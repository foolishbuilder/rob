"""Privacy / right-to-erasure repository.

:class:`UserDataRepository` removes *all* of a Discord user's Rob data, either
everywhere (all guilds) or scoped to a single guild. It deliberately leaves two
things untouched:

* ``bot_users`` — this holds the allow/block status. A blocked user must stay
  blocked even after erasing the rest of their footprint.
* ``the_count`` — only stores a single ``last_user_id`` integer for a guild's
  counting channel; there is no per-user row to remove.

Every erasure runs inside a single transaction so a partial wipe can never be
left behind. Each method returns a ``{table: rows_deleted}`` mapping for the
caller to surface in the confirmation summary and the audit log.

The set of tables / columns mirrors the v2 build scripts under
``scripts/db/build`` (001 core, 004 sub send names, 005 count recovery,
006 send change requests, 008 dm preferences, 009 terms acceptance).
"""

from __future__ import annotations

from asyncpg import Connection

from rob.database.connection import Database


def _rows_affected(status: str) -> int:
    """Parse asyncpg's ``DELETE <n>`` command tag into ``<n>``."""

    parts = status.split()
    if not parts:
        return 0
    try:
        return int(parts[-1])
    except ValueError:
        return 0


class UserDataRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    # -- public API -----------------------------------------------------------

    async def delete_user_everywhere(self, discord_user_id: int) -> dict[str, int]:
        """Hard-delete every row tied to ``discord_user_id`` across all guilds.

        Runs in one transaction. ``user_terms_acceptance`` (which is not
        guild-scoped) is purged here as well. Returns ``{table: rows_deleted}``.
        """

        async with self.database.transaction() as connection:
            deleted = await self._delete_guild_scoped(
                connection,
                discord_user_id=discord_user_id,
                guild_id=None,
            )
            deleted["user_terms_acceptance"] = _rows_affected(
                await connection.execute(
                    "DELETE FROM user_terms_acceptance WHERE discord_user_id = $1",
                    discord_user_id,
                )
            )
        return deleted

    async def delete_user_in_guild(
        self, discord_user_id: int, guild_id: int
    ) -> dict[str, int]:
        """Hard-delete every row tied to ``discord_user_id`` within ``guild_id``.

        Every DELETE is additionally constrained by ``guild_id``. The
        ``user_terms_acceptance`` table has no guild column, so it is left alone
        in the single-guild case. Returns ``{table: rows_deleted}``.
        """

        async with self.database.transaction() as connection:
            return await self._delete_guild_scoped(
                connection,
                discord_user_id=discord_user_id,
                guild_id=guild_id,
            )

    async def guilds_with_user_data(self, discord_user_id: int) -> list[int]:
        """Return the distinct guild ids where the user has any Rob data.

        Used to decide whether the ``/forgetme`` confirmation should offer a
        "this server vs everywhere" scope choice. ``user_terms_acceptance`` is
        intentionally excluded because it carries no guild and would not change
        the per-guild decision.
        """

        async with self.database.acquire() as connection:
            rows = await connection.fetch(
                """
                SELECT DISTINCT guild_id FROM (
                    SELECT guild_id FROM dommes WHERE discord_user_id = $1
                    UNION ALL
                    SELECT guild_id FROM subs WHERE discord_user_id = $1
                    UNION ALL
                    SELECT guild_id FROM sends
                        WHERE domme_user_id = $1 OR sub_user_id = $1
                    UNION ALL
                    SELECT guild_id FROM count_blocks WHERE discord_user_id = $1
                    UNION ALL
                    SELECT guild_id FROM count_recovery_windows
                        WHERE failed_user_id = $1 OR required_domme_user_id = $1
                    UNION ALL
                    SELECT guild_id FROM send_change_requests
                        WHERE domme_user_id = $1 OR approved_by_user_id = $1
                    UNION ALL
                    SELECT guild_id FROM domme_onboarding_state
                        WHERE discord_user_id = $1
                ) AS guilds
                WHERE guild_id IS NOT NULL
                ORDER BY guild_id
                """,
                discord_user_id,
            )
        return [int(row["guild_id"]) for row in rows]

    # -- internals ------------------------------------------------------------

    async def _delete_guild_scoped(
        self,
        connection: Connection,
        *,
        discord_user_id: int,
        guild_id: int | None,
    ) -> dict[str, int]:
        """Run every guild-scoped DELETE for the user on ``connection``.

        When ``guild_id`` is ``None`` the deletes span all guilds (the
        "everywhere" case); otherwise each statement is additionally constrained
        to ``guild_id``. ``user_terms_acceptance`` is *not* handled here — it has
        no guild column and is only purged in the everywhere case by the caller.
        """

        # ``$2`` is only referenced when guild_filter is non-empty, so the
        # parameter tuple is built to match.
        guild_filter = "" if guild_id is None else " AND guild_id = $2"
        scope: tuple = (discord_user_id,) if guild_id is None else (discord_user_id, guild_id)

        deleted: dict[str, int] = {}

        # sub_send_names cascades from subs via FK ON DELETE CASCADE, but the
        # rows are deleted explicitly first so the returned count is accurate
        # and the wipe does not rely on cascade being enabled in every env.
        deleted["sub_send_names"] = _rows_affected(
            await connection.execute(
                f"DELETE FROM sub_send_names WHERE discord_user_id = $1{guild_filter}",
                *scope,
            )
        )
        deleted["subs"] = _rows_affected(
            await connection.execute(
                f"DELETE FROM subs WHERE discord_user_id = $1{guild_filter}",
                *scope,
            )
        )
        deleted["dommes"] = _rows_affected(
            await connection.execute(
                f"DELETE FROM dommes WHERE discord_user_id = $1{guild_filter}",
                *scope,
            )
        )
        deleted["sends"] = _rows_affected(
            await connection.execute(
                "DELETE FROM sends "
                f"WHERE (domme_user_id = $1 OR sub_user_id = $1){guild_filter}",
                *scope,
            )
        )
        deleted["count_blocks"] = _rows_affected(
            await connection.execute(
                f"DELETE FROM count_blocks WHERE discord_user_id = $1{guild_filter}",
                *scope,
            )
        )
        deleted["count_recovery_windows"] = _rows_affected(
            await connection.execute(
                "DELETE FROM count_recovery_windows "
                f"WHERE (failed_user_id = $1 OR required_domme_user_id = $1){guild_filter}",
                *scope,
            )
        )
        deleted["send_change_requests"] = _rows_affected(
            await connection.execute(
                "DELETE FROM send_change_requests "
                f"WHERE (domme_user_id = $1 OR approved_by_user_id = $1){guild_filter}",
                *scope,
            )
        )
        deleted["domme_onboarding_state"] = _rows_affected(
            await connection.execute(
                f"DELETE FROM domme_onboarding_state WHERE discord_user_id = $1{guild_filter}",
                *scope,
            )
        )
        deleted["bot_settings"] = await self._delete_bot_settings(
            connection,
            discord_user_id=discord_user_id,
            guild_id=guild_id,
        )
        return deleted

    async def _delete_bot_settings(
        self,
        connection: Connection,
        *,
        discord_user_id: int,
        guild_id: int | None,
    ) -> int:
        """Delete per-user ``bot_settings`` key/value rows.

        Keys follow ``activity:{guild}:user:{uid}:%`` and
        ``inactivity:{guild}:user:{uid}:%``. When ``guild_id`` is ``None`` the
        ``{guild}`` segment is wildcarded so every guild's per-user keys go.
        ``\\`` is escaped to ``\\\\`` so a literal ``\`` in an id (there never is
        one, but defensively) can't act as a LIKE escape.
        """

        guild_segment = "%" if guild_id is None else str(int(guild_id))
        uid = int(discord_user_id)
        activity_pattern = f"activity:{guild_segment}:user:{uid}:%"
        inactivity_pattern = f"inactivity:{guild_segment}:user:{uid}:%"
        status = await connection.execute(
            "DELETE FROM bot_settings WHERE key LIKE $1 OR key LIKE $2",
            activity_pattern,
            inactivity_pattern,
        )
        return _rows_affected(status)
