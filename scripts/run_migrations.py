from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any

from rob.config.settings import configure_logging, load_base_settings
from rob.database.connection import Database

MIGRATIONS_DIR = Path(__file__).resolve().parents[1] / "rob" / "database" / "migrations"


def resolve_migration_database_url(settings: object | None = None) -> str:
    value = (os.getenv("MIGRATION_DATABASE_URL") or "").strip()
    if value:
        return value
    if settings is not None:
        fallback = str(getattr(settings, "database_url", "") or "").strip()
        if fallback:
            return fallback
    runtime_fallback = (os.getenv("DATABASE_URL") or "").strip()
    if runtime_fallback:
        return runtime_fallback
    raise RuntimeError(
        "Missing required environment variable: MIGRATION_DATABASE_URL "
        "(or DATABASE_URL fallback)."
    )


def load_migration_settings() -> tuple[str, Any | None]:
    try:
        settings = load_base_settings()
    except RuntimeError as exc:
        if "Missing required environment variable: DATABASE_URL" not in str(exc):
            raise
        log_level = (os.getenv("LOG_LEVEL") or "INFO").strip() or "INFO"
        return log_level, None
    return settings.log_level, settings


async def main() -> None:
    log_level, settings = load_migration_settings()
    configure_logging(log_level)

    database = Database(resolve_migration_database_url(settings))
    await database.connect()

    try:
        migration_files = sorted(MIGRATIONS_DIR.glob("*.sql"))

        if not migration_files:
            raise RuntimeError("No migration files found.")
        
        async with database.transaction() as connection:
            await connection.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version TEXT PRIMARY KEY,
                    applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
                );
                """
            )

            rows = await connection.fetch(
                "SELECT version FROM schema_migrations;"
            )
            applied_versions = {row["version"] for row in rows}

            for migration_file in migration_files:
                version = migration_file.stem

                if version in applied_versions:
                    print(f"Skipping {version}; already applied.")
                    continue

                sql = migration_file.read_text(encoding="utf-8")

                print(f"Applying {version}...")
                await connection.execute(sql)
                await connection.execute(
                    """
                    INSERT INTO schema_migrations (version)
                    VALUES ($1);
                    """,
                    version,
                )

        print("Migrations complete.")
    finally:
        await database.close()

if __name__ == "__main__":
    asyncio.run(main())
