from __future__ import annotations

import asyncio
import os
from pathlib import Path

from rob.config.settings import configure_logging, load_base_settings
from rob.database.connection import Database

MIGRATIONS_DIR = Path(__file__).resolve().parents[1] / "rob" / "database" / "migrations"


def resolve_migration_database_url(settings: object) -> str:
    value = (os.getenv("MIGRATION_DATABASE_URL") or "").strip()
    if value:
        return value
    return str(settings.database_url)


async def main() -> None:
    settings = load_base_settings()
    configure_logging(settings.log_level)

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
