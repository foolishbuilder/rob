from __future__ import annotations

from asyncpg import Record

from rob.database.connection import Database
from rob.database.repositories.models import (
    LeaderboardEntry,
    LeaderboardMessageRef,
    LeaderboardSummary,
)


def _build_message_ref(row: Record) -> LeaderboardMessageRef:
    return LeaderboardMessageRef(
        id=int(row["id"]),
        guild_id=int(row["guild_id"]),
        message_key=str(row["message_key"]),
        leaderboard_type=row["leaderboard_type"],
        channel_id=int(row["channel_id"]),
        message_id=int(row["message_id"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


class LeaderboardsRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    async def get_summary(self, guild_id: int) -> LeaderboardSummary:
        async with self.database.acquire() as connection:
            row = await connection.fetchrow(
                """
                SELECT
                    COALESCE(SUM(amount_cents), 0) AS total_cents,
                    COUNT(*) AS send_count,
                    COUNT(DISTINCT domme_user_id) AS domme_count,
                    COUNT(DISTINCT sub_user_id) FILTER (WHERE sub_user_id IS NOT NULL) AS sub_count,
                    COUNT(*) FILTER (WHERE sub_user_id IS NULL) AS unclaimed_send_count,
                    COALESCE(SUM(amount_cents) FILTER (WHERE sub_user_id IS NULL), 0) AS unclaimed_total_cents
                FROM sends
                WHERE guild_id = $1
                AND discord_post_status = 'posted'
                """,
                guild_id,
            )
        assert row is not None
        return LeaderboardSummary(
            total_cents=int(row["total_cents"] or 0),
            send_count=int(row["send_count"] or 0),
            domme_count=int(row["domme_count"] or 0),
            sub_count=int(row["sub_count"] or 0),
            unclaimed_send_count=int(row["unclaimed_send_count"] or 0),
            unclaimed_total_cents=int(row["unclaimed_total_cents"] or 0),
        )

    async def get_top_dommes(self, guild_id: int, *, limit: int = 10) -> list[LeaderboardEntry]:
        async with self.database.acquire() as connection:
            rows = await connection.fetch(
                """
                SELECT
                    domme_user_id AS user_id,
                    COALESCE(SUM(amount_cents), 0) AS total_cents,
                    COUNT(*) AS send_count
                FROM sends
                WHERE guild_id = $1
                AND discord_post_status = 'posted'
                GROUP BY domme_user_id
                ORDER BY total_cents DESC, send_count DESC, domme_user_id ASC
                LIMIT $2
                """,
                guild_id,
                limit,
            )
        return [
            LeaderboardEntry(
                label=f"<@{int(row['user_id'])}>",
                user_id=int(row["user_id"]),
                total_cents=int(row["total_cents"] or 0),
                send_count=int(row["send_count"] or 0),
            )
            for row in rows
        ]

    async def get_top_subs(self, guild_id: int, *, limit: int = 10) -> list[LeaderboardEntry]:
        async with self.database.acquire() as connection:
            rows = await connection.fetch(
                """
                SELECT
                    sends.sub_user_id AS user_id,
                    MIN(subs.send_name) AS send_name,
                    COALESCE(SUM(sends.amount_cents), 0) AS total_cents,
                    COUNT(*) AS send_count
                FROM sends
                JOIN subs ON subs.id = sends.sub_id
                WHERE sends.guild_id = $1
                AND sends.discord_post_status = 'posted'
                AND sends.sub_user_id IS NOT NULL
                GROUP BY sends.sub_user_id
                ORDER BY total_cents DESC, send_count DESC, sends.sub_user_id ASC
                LIMIT $2
                """,
                guild_id,
                limit,
            )
        return [
            LeaderboardEntry(
                label=f"<@{int(row['user_id'])}>",
                user_id=int(row["user_id"]),
                total_cents=int(row["total_cents"] or 0),
                send_count=int(row["send_count"] or 0),
            )
            for row in rows
        ]

    async def get_message(self, guild_id: int, message_key: str) -> LeaderboardMessageRef | None:
        async with self.database.acquire() as connection:
            row = await connection.fetchrow(
                """
                SELECT *
                FROM leaderboard_messages
                WHERE guild_id = $1
                AND message_key = $2
                """,
                guild_id,
                message_key,
            )
        if row is None:
            return None
        return _build_message_ref(row)

    async def upsert_message(
        self,
        *,
        guild_id: int,
        message_key: str,
        leaderboard_type: str | None,
        channel_id: int,
        message_id: int,
    ) -> LeaderboardMessageRef:
        async with self.database.acquire() as connection:
            row = await connection.fetchrow(
                """
                INSERT INTO leaderboard_messages (
                    guild_id,
                    message_key,
                    leaderboard_type,
                    channel_id,
                    message_id
                )
                VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT (guild_id, message_key) DO UPDATE SET
                    leaderboard_type = EXCLUDED.leaderboard_type,
                    channel_id = EXCLUDED.channel_id,
                    message_id = EXCLUDED.message_id,
                    updated_at = now()
                RETURNING *
                """,
                guild_id,
                message_key,
                leaderboard_type,
                channel_id,
                message_id,
            )
        assert row is not None
        return _build_message_ref(row)
