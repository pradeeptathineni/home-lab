from __future__ import annotations

import pytest

from labctl.cli import _run_script, build_parser, main
from labctl.runner import CommandRunner


def test_parser_accepts_known_profile() -> None:
    args = build_parser().parse_args(["deploy", "core"])
    assert args.profile == "core"


def test_parser_rejects_unknown_profile() -> None:
    with pytest.raises(SystemExit):
        build_parser().parse_args(["deploy", "everything"])


def test_dry_run_prints_underlying_command(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("LABCTL_TARGET", "local")
    assert main(["--dry-run", "deploy", "core"]) == 0
    output = capsys.readouterr().out
    assert "docker compose" in output
    assert "--profile core up -d --wait" in output


def test_invalid_service_returns_nonzero() -> None:
    assert main(["--dry-run", "logs", "../secret"]) != 0


def test_restore_test_is_non_destructive_by_default(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--dry-run", "backup", "restore-test"]) == 0
    assert "--allow-local-repository" not in capsys.readouterr().out


def test_secret_init_runs_inside_lima(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--dry-run", "secrets", "init"]) == 0
    output = capsys.readouterr().out
    assert "limactl shell" in output
    assert "init_runtime_env.py" in output


def test_script_preserves_not_tested_exit_code(
    tmp_path,
) -> None:
    script = tmp_path / "not_tested.py"
    script.write_text("raise SystemExit(3)\n")
    assert _run_script(tmp_path, CommandRunner(), script.name) == 3
