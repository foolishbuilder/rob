from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_portal_install_script_uses_app_root_pattern_like_other_installers():
    script = (REPO_ROOT / "deploy" / "scripts" / "install-portal-dev.sh").read_text(encoding="utf-8")
    assert 'APP_ROOT="${APP_ROOT:-/opt/rob-portal}"' in script
    assert 'APP_DIR="${APP_DIR:-${APP_ROOT}/app}"' in script


def test_portal_install_script_installs_deploy_symlink():
    script = (REPO_ROOT / "deploy" / "scripts" / "install-portal-dev.sh").read_text(encoding="utf-8")
    assert 'DEPLOY_SCRIPT_LINK="${DEPLOY_SCRIPT_LINK:-${APP_ROOT}/deploy-portal-dev.sh}"' in script
    assert 'ln -sfn "${APP_DIR}/${DEPLOY_SCRIPT_SOURCE_REL}" "${DEPLOY_SCRIPT_LINK}"' in script
