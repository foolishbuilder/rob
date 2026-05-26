from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace

from scripts import run_migrations


class _FakeConnection:
    def __init__(self):
        self.executed: list[tuple[str, tuple[object, ...]]] = []

    async def execute(self, query: str, *params):
        self.executed.append((query, params))

    async def fetch(self, query: str, *params):
        del query, params
        return []


class _FakeDatabase:
    created_urls: list[str] = []

    def __init__(self, database_url: str):
        self.database_url = database_url
        self.connection = _FakeConnection()
        _FakeDatabase.created_urls.append(database_url)

    async def connect(self):
        return None

    async def close(self):
        return None

    @asynccontextmanager
    async def transaction(self):
        yield self.connection


def test_resolve_migration_database_url_prefers_env(monkeypatch):
    monkeypatch.setenv("MIGRATION_DATABASE_URL", "postgresql://migrator/db")
    settings = SimpleNamespace(database_url="postgresql://runtime/db")
    assert run_migrations.resolve_migration_database_url(settings) == "postgresql://migrator/db"


def test_resolve_migration_database_url_falls_back_to_database_url(monkeypatch):
    monkeypatch.delenv("MIGRATION_DATABASE_URL", raising=False)
    settings = SimpleNamespace(database_url="postgresql://runtime/db")
    assert run_migrations.resolve_migration_database_url(settings) == "postgresql://runtime/db"


def test_run_migrations_uses_migration_database_url_when_set(monkeypatch, tmp_path):
    migration_file = tmp_path / "001_example.sql"
    migration_file.write_text("SELECT 1;\n", encoding="utf-8")

    _FakeDatabase.created_urls = []
    monkeypatch.setenv("MIGRATION_DATABASE_URL", "postgresql://migrator/db")
    monkeypatch.setattr(run_migrations, "MIGRATIONS_DIR", tmp_path)
    monkeypatch.setattr(
        run_migrations,
        "load_base_settings",
        lambda: SimpleNamespace(log_level="INFO", database_url="postgresql://runtime/db"),
    )
    monkeypatch.setattr(run_migrations, "configure_logging", lambda _level: None)
    monkeypatch.setattr(run_migrations, "Database", _FakeDatabase)

    asyncio.run(run_migrations.main())

    assert _FakeDatabase.created_urls == ["postgresql://migrator/db"]
