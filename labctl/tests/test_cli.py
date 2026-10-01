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


def test_parser_accepts_ai_operations() -> None:
    args = build_parser().parse_args(["ai", "benchmark", "qwen35-2b-q4km"])
    assert args.ai_command == "benchmark"
    assert args.model == "qwen35-2b-q4km"
    retrieval = build_parser().parse_args(["ai", "retrieval", "qwen3-embed-0.6b-q8"])
    assert retrieval.ai_command == "retrieval"
    route = build_parser().parse_args(["ai", "route", "start"])
    assert route.operation == "start"
    webui = build_parser().parse_args(["ai", "webui", "configure"])
    assert webui.operation == "configure"
    comparison = build_parser().parse_args(["ai", "compare"])
    assert comparison.ai_command == "compare"


def test_ai_fetch_dry_run_is_visible(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path
) -> None:
    monkeypatch.setenv("HOME_LAB_MODEL_ROOT", str(tmp_path / "models"))
    assert main(["--dry-run", "ai", "fetch", "granite4-1b-q4km"]) == 0
    output = capsys.readouterr().out
    assert "Proposed model download" in output
    assert "curl --fail --location" in output


def test_parser_accepts_sandbox_experiment() -> None:
    args = build_parser().parse_args(["sandbox", "experiment", "network-fault"])
    assert args.sandbox_command == "experiment"
    assert args.experiment == "network-fault"
