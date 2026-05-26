from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_database_docs_reference_separated_bot_and_webhook_users():
    architecture_doc = (REPO_ROOT / "docs" / "database-architecture.md").read_text(encoding="utf-8")
    assert "rob_dev_bot" in architecture_doc
    assert "rob_dev_webhook" in architecture_doc
    assert "rob_prod_bot" in architecture_doc
    assert "rob_prod_webhook" in architecture_doc


def test_env_example_includes_migration_database_url():
    env_example = (REPO_ROOT / ".env.example").read_text(encoding="utf-8")
    assert "MIGRATION_DATABASE_URL" in env_example
