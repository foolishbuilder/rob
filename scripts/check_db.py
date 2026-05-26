from __future__ import annotations

import asyncio
from pathlib import Path

from rob.config.settings import configure_logging, load_base_settings
from rob.database.connection import Database

MIGRATIONS_DIR = Path(__file__).resolve().parents[1] / "rob" / "database" / "migrations"

REQUIRED_TABLE_COLUMNS: dict[str, set[str]] = {
    "guild_settings": {
        "guild_id",
        "domme_role_id",
        "sub_role_id",
        "warn_log_channel_id",
        "carlbot_user_id",
        "report_channel_id",
        "inactive_role_id",
    },
    "sends": {
        "id",
        "domme_user_id",
        "sub_user_id",
        "sub_name",
        "amount_cents",
        "currency",
        "discord_post_status",
        "is_test_send",
        "public_send_id",
    },
    "send_requests": {
        "id",
        "guild_id",
        "sub_user_id",
        "domme_user_id",
        "method",
        "status",
        "denial_reason",
        "resolved_by_user_id",
    },
    "leaderboard_message": {
        "guild_id",
        "message_key",
        "leaderboard_type",
        "channel_id",
        "message_id",
    },
}

BOT_TABLE_PERMISSIONS: dict[str, tuple[str, ...]] = {
    "blacklist": ("SELECT", "INSERT", "UPDATE", "DELETE"),
    "bot_state": ("SELECT", "INSERT", "UPDATE", "DELETE"),
    "counting_state": ("SELECT", "INSERT", "UPDATE", "DELETE"),
    "dommes": ("SELECT", "INSERT", "UPDATE", "DELETE"),
    "guild_settings": ("SELECT", "INSERT", "UPDATE", "DELETE"),
    "leaderboard_message": ("SELECT", "INSERT", "UPDATE", "DELETE"),
    "public_leaderboards": ("SELECT", "INSERT", "UPDATE", "DELETE"),
    "schema_migrations": ("SELECT",),
    "send_requests": ("SELECT", "INSERT", "UPDATE", "DELETE"),
    "sends": ("SELECT", "INSERT", "UPDATE", "DELETE"),
    "subs": ("SELECT", "INSERT", "UPDATE", "DELETE"),
    "throne_creators": ("SELECT", "INSERT", "UPDATE", "DELETE"),
}

WEBHOOK_TABLE_PERMISSIONS: dict[str, tuple[str, ...]] = {
    "guild_settings": ("SELECT",),
    "dommes": ("SELECT",),
    "subs": ("SELECT",),
    "public_leaderboards": ("SELECT",),
    "leaderboard_message": ("SELECT",),
    "schema_migrations": ("SELECT",),
    "throne_creators": ("SELECT", "UPDATE"),
    "bot_state": ("SELECT", "UPDATE"),
    "sends": ("SELECT", "INSERT", "UPDATE"),
}


async def _assert_table_columns(connection, table: str, required_columns: set[str]) -> None:
    rows = await connection.fetch(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public'
        AND table_name = $1
        """,
        table,
    )
    if not rows:
        raise RuntimeError(f"Missing required table: {table}")
    present = {str(row["column_name"]) for row in rows}
    missing = sorted(required_columns - present)
    if missing:
        raise RuntimeError(f"Table {table} is missing required columns: {', '.join(missing)}")


async def _table_exists(connection, table: str) -> bool:
    value = await connection.fetchval(
        "SELECT to_regclass($1) IS NOT NULL",
        f"public.{table}",
    )
    return bool(value)


async def _dommes_has_public_display_columns(connection) -> bool:
    rows = await connection.fetch(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'dommes'
          AND column_name IN ('public_display_name', 'public_display_name_updated_at')
        """,
    )
    columns = {str(row["column_name"]) for row in rows}
    return {
        "public_display_name",
        "public_display_name_updated_at",
    }.issubset(columns)


def _runtime_profile(current_user: str) -> str:
    if current_user.endswith("_webhook"):
        return "webhook"
    if current_user.endswith("_bot"):
        return "bot"
    return "generic"


async def _assert_runtime_permissions(connection, *, current_user: str, current_database: str) -> None:
    if not await connection.fetchval(
        "SELECT has_database_privilege(current_user, current_database(), 'CONNECT')",
    ):
        raise RuntimeError(
            f"Runtime user '{current_user}' cannot CONNECT to database '{current_database}'."
        )

    profile = _runtime_profile(current_user)
    required = BOT_TABLE_PERMISSIONS if profile in {"bot", "generic"} else WEBHOOK_TABLE_PERMISSIONS
    missing: list[str] = []

    for table_name, privileges in required.items():
        for privilege in privileges:
            has_privilege = await connection.fetchval(
                "SELECT has_table_privilege(current_user, $1, $2)",
                f"public.{table_name}",
                privilege,
            )
            if not has_privilege:
                missing.append(f"{table_name}:{privilege}")

    sequence_name = "public.sends_id_seq"
    for privilege in ("USAGE", "SELECT", "UPDATE"):
        has_privilege = await connection.fetchval(
            "SELECT has_sequence_privilege(current_user, $1, $2)",
            sequence_name,
            privilege,
        )
        if not has_privilege:
            missing.append(f"sends_id_seq:{privilege}")

    if missing:
        raise RuntimeError(
            "Runtime permission check failed for user "
            f"'{current_user}'. Missing privileges: {', '.join(missing)}"
        )

    if profile == "webhook":
        has_delete = await connection.fetchval(
            "SELECT has_table_privilege(current_user, 'public.sends', 'DELETE')",
        )
        if has_delete:
            raise RuntimeError(
                "Webhook runtime user has DELETE on public.sends, which is broader than intended."
            )


async def main() -> None:
    settings = load_base_settings()
    configure_logging(settings.log_level)

    database = Database(settings.database_url)

    await database.connect()

    try:
        healthy = await database.health_check()
        if not healthy:
            raise RuntimeError("Database check failed.")
        async with database.acquire() as connection:
            current_user = str(await connection.fetchval("SELECT current_user"))
            current_database = str(await connection.fetchval("SELECT current_database()"))

            if not await _table_exists(connection, "schema_migrations"):
                raise RuntimeError("Missing required table: schema_migrations")

            rows = await connection.fetch("SELECT version FROM schema_migrations")
            applied = {str(row["version"]) for row in rows}

            migration_files = sorted(MIGRATIONS_DIR.glob("*.sql"))
            expected = {migration_file.stem for migration_file in migration_files}
            missing_migrations = sorted(expected - applied)
            if missing_migrations:
                if (
                    "009_domme_public_display_names" in missing_migrations
                    and await _dommes_has_public_display_columns(connection)
                ):
                    raise RuntimeError(
                        "Migration 009_domme_public_display_names is missing from "
                        "schema_migrations, but dommes columns already exist. "
                        "Repair with: "
                        "INSERT INTO schema_migrations (version, applied_at) "
                        "VALUES ('009_domme_public_display_names', now()) "
                        "ON CONFLICT (version) DO NOTHING;"
                    )
                raise RuntimeError(
                    "Database is missing applied migrations: " + ", ".join(missing_migrations)
                )

            for table_name, required_columns in REQUIRED_TABLE_COLUMNS.items():
                await _assert_table_columns(connection, table_name, required_columns)

            if await _table_exists(connection, "leaderboard_messages"):
                raise RuntimeError(
                    "Legacy table leaderboard_messages detected. "
                    "Run scripts/db/06_cleanup_legacy_tables.sql and migrate rows before dropping it."
                )

            await _assert_runtime_permissions(
                connection,
                current_user=current_user,
                current_database=current_database,
            )

        print("Database check passed.")
    finally:
        await database.close()

if __name__ == "__main__":
    asyncio.run(main())
