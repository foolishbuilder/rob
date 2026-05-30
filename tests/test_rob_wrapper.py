from __future__ import annotations

import os
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_fake_command(tmp_path: Path, name: str, body: str) -> Path:
    command_path = tmp_path / name
    command_path.write_text(body, encoding="utf-8")
    command_path.chmod(0o755)
    return command_path


def test_rob_wrapper_uses_http_ops_without_python(tmp_path: Path):
    log_path = tmp_path / "curl.log"
    _write_fake_command(
        tmp_path,
        "curl",
        "#!/usr/bin/env bash\n"
        "printf '%s\\n' \"$*\" >> \"$ROB_TEST_LOG\"\n"
        "printf '{\"ok\":true}\\n200'\n",
    )
    symlink_path = tmp_path / "rob"
    symlink_path.symlink_to(REPO_ROOT / "scripts" / "rob")

    env = os.environ.copy()
    env["PATH"] = f"{tmp_path}:{env['PATH']}"
    env["ROB_TEST_LOG"] = str(log_path)

    result = subprocess.run(
        [str(symlink_path), "maintenance", "status"],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )

    assert '{"ok":true}' in result.stdout
    assert "http://127.0.0.1:8811/maintenance" in log_path.read_text(encoding="utf-8")


def test_rob_wrapper_lists_dommes_via_psql_without_python(tmp_path: Path):
    log_path = tmp_path / "psql.log"
    _write_fake_command(
        tmp_path,
        "psql",
        "#!/usr/bin/env bash\n"
        "printf '%s\\n' \"$*\" >> \"$ROB_TEST_LOG\"\n"
        "printf '123\\tMistress\\tmistress\\tactive\\tactive\\n'\n",
    )
    symlink_path = tmp_path / "rob"
    symlink_path.symlink_to(REPO_ROOT / "scripts" / "rob")

    env = os.environ.copy()
    env["PATH"] = f"{tmp_path}:{env['PATH']}"
    env["ROB_TEST_LOG"] = str(log_path)
    env["DATABASE_URL"] = "postgresql://runtime/db"

    result = subprocess.run(
        [str(symlink_path), "dommes", "list", "--guild", "42"],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )

    assert "Mistress" in result.stdout
    assert "guild_id=42" in log_path.read_text(encoding="utf-8")


def test_robctl_wrapper_resolves_real_repo_root_from_symlink(tmp_path: Path):
    log_path = tmp_path / "curl.log"
    _write_fake_command(
        tmp_path,
        "curl",
        "#!/usr/bin/env bash\n"
        "printf '%s\\n' \"$*\" >> \"$ROB_TEST_LOG\"\n"
        "printf '{\"ok\":true}\\n200'\n",
    )
    symlink_path = tmp_path / "robctl"
    symlink_path.symlink_to(REPO_ROOT / "scripts" / "robctl")

    env = os.environ.copy()
    env["PATH"] = f"{tmp_path}:{env['PATH']}"
    env["ROB_TEST_LOG"] = str(log_path)

    result = subprocess.run(
        [str(symlink_path), "block", "123"],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )

    assert '{"ok":true}' in result.stdout
    assert "/block" in log_path.read_text(encoding="utf-8")


def test_rob_wrapper_no_longer_invokes_scripts_ops():
    wrapper = (REPO_ROOT / "scripts" / "rob").read_text(encoding="utf-8")
    assert "scripts.ops" not in wrapper
    assert "PYTHON_BIN" not in wrapper
