from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_portal_deploy_workflow_uses_webhook_ssh_secrets():
    workflow = (REPO_ROOT / ".github" / "workflows" / "deploy-portal-dev.yml").read_text(encoding="utf-8")

    assert "secrets.WEBHOOK_DEV_HOST" in workflow
    assert "secrets.WEBHOOK_DEV_USER" in workflow
    assert "secrets.WEBHOOK_DEV_SSH_KEY" in workflow
    assert "secrets.WEBHOOK_DEV_PORT" in workflow
