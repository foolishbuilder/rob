from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest

from scripts import check_db


def _required_columns_with_overrides(overrides: dict[str, set[str]] | None = None) -> dict[str, set[str]]:
    columns = {name: set(values) for name, values in check_db.REQUIRED_TABLE_COLUMNS.items()}
    for table_name, table_columns in (overrides or {}).items():
        columns[table_name] = set(table_columns)
    return columns


class _FakeConnection:
    def __init__(
        self,
        *,
        applied_versions: list[str],
        table_columns: dict[str, set[str]],
        dommes_public_columns: bool = False,
        legacy_table_exists: bool = False,
        current_user: str = "rob_dev_bot",
        current_database: str = "rob_dev",
    ):
        self.applied_versions = applied_versions
        self.table_columns = table_columns
        self.dommes_public_columns = dommes_public_columns
        self.legacy_table_exists = legacy_table_exists
        self.current_user = current_user
        self.current_database = current_database

    async def fetch(self, query: str, *params):
        if query.strip().startswith("SELECT version FROM schema_migrations"):
            return [{"version": version} for version in self.applied_versions]
        if "FROM information_schema.columns" in query and "table_name = 'dommes'" in query:
            if not self.dommes_public_columns:
                return []
            return [
                {"column_name": "public_display_name"},
                {"column_name": "public_display_name_updated_at"},
            ]
        if "FROM information_schema.columns" in query and "table_name = $1" in query:
            table_name = str(params[0])
            return [{"column_name": column_name} for column_name in sorted(self.table_columns.get(table_name, set()))]
        return []

    async def fetchval(self, query: str, *params):
        if query.strip() == "SELECT current_user":
            return self.current_user
        if query.strip() == "SELECT current_database()":
            return self.current_database
        if "to_regclass" in query:
            relation = str(params[0])
            if relation == "public.schema_migrations":
                return True
            if relation == "public.leaderboard_messages":
                return self.legacy_table_exists
            table_name = relation.removeprefix("public.")
            return table_name in self.table_columns
        if "has_database_privilege" in query:
            return True
        if "has_table_privilege" in query:
            if "'public.sends', 'DELETE'" in query:
                return False
            return True
        if "has_sequence_privilege" in query:
            return True
        return None


class _FakeDatabase:
    def __init__(self, _database_url: str, *, connection: _FakeConnection):
        self.connection = connection

    async def connect(self):
        return None

    async def close(self):
        return None

    async def health_check(self) -> bool:
        return True

    @asynccontextmanager
    async def acquire(self):
        yield self.connection


def _patch_check_db(monkeypatch: pytest.MonkeyPatch, *, connection: _FakeConnection, migrations_dir):
    monkeypatch.setattr(check_db, "MIGRATIONS_DIR", migrations_dir)
    monkeypatch.setattr(
        check_db,
        "load_base_settings",
        lambda: SimpleNamespace(log_level="INFO", database_url="postgresql://runtime/db"),
    )
    monkeypatch.setattr(check_db, "configure_logging", lambda _level: None)
    monkeypatch.setattr(
        check_db,
        "Database",
        lambda database_url: _FakeDatabase(database_url, connection=connection),
    )


def test_check_db_detects_missing_migrations(monkeypatch: pytest.MonkeyPatch, tmp_path):
    (tmp_path / "001_initial.sql").write_text("SELECT 1;\n", encoding="utf-8")
    (tmp_path / "009_domme_public_display_names.sql").write_text("SELECT 1;\n", encoding="utf-8")
    connection = _FakeConnection(
        applied_versions=["001_initial"],
        table_columns=_required_columns_with_overrides(),
        dommes_public_columns=False,
    )
    _patch_check_db(monkeypatch, connection=connection, migrations_dir=tmp_path)

    with pytest.raises(RuntimeError, match="Database is missing applied migrations"):
        asyncio.run(check_db.main())


def test_check_db_detects_missing_required_columns(monkeypatch: pytest.MonkeyPatch, tmp_path):
    (tmp_path / "001_initial.sql").write_text("SELECT 1;\n", encoding="utf-8")
    columns = _required_columns_with_overrides(
        {
            "sends": {
                "id",
                "domme_user_id",
                "sub_user_id",
                "sub_name",
                "amount_cents",
                "currency",
                "discord_post_status",
                "is_test_send",
            }
        }
    )
    connection = _FakeConnection(
        applied_versions=["001_initial"],
        table_columns=columns,
        dommes_public_columns=False,
    )
    _patch_check_db(monkeypatch, connection=connection, migrations_dir=tmp_path)

    with pytest.raises(RuntimeError, match="Table sends is missing required columns"):
        asyncio.run(check_db.main())


def test_check_db_reports_009_recording_repair_when_columns_exist(monkeypatch: pytest.MonkeyPatch, tmp_path):
    (tmp_path / "001_initial.sql").write_text("SELECT 1;\n", encoding="utf-8")
    (tmp_path / "009_domme_public_display_names.sql").write_text("SELECT 1;\n", encoding="utf-8")
    connection = _FakeConnection(
        applied_versions=["001_initial"],
        table_columns=_required_columns_with_overrides(),
        dommes_public_columns=True,
    )
    _patch_check_db(monkeypatch, connection=connection, migrations_dir=tmp_path)

    with pytest.raises(RuntimeError, match="Migration 009_domme_public_display_names is missing"):
        asyncio.run(check_db.main())


def test_repo_migrations_include_009_domme_public_display_names():
    expected = {path.stem for path in check_db.MIGRATIONS_DIR.glob("*.sql")}
    assert "009_domme_public_display_names" in expected
