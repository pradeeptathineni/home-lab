from pathlib import Path

import pytest

from labctl.compose import compose_command, profiles_arguments, validate_profile, validate_service


def test_local_compose_command_is_explicit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LAB_ENV_FILE", "/private/lab.env")
    command = compose_command(Path("/repo"), ["config"], execution_target="local")
    assert command == [
        "docker",
        "compose",
        "--project-directory",
        "/repo",
        "--env-file",
        "/private/lab.env",
        "-f",
        "/repo/compose.yaml",
        "config",
    ]


def test_lima_compose_command_uses_read_only_repo_path() -> None:
    command = compose_command(Path("/host/repo"), ["ps"], execution_target="lima")
    assert command[:5] == ["limactl", "shell", "--workdir", "/host/repo", "home-lab"]
    assert "/host/repo/compose.yaml" in command
    assert "/srv/home-lab/secrets/runtime.env" in command


def test_profile_and_service_validation() -> None:
    assert validate_profile("core") == "core"
    assert validate_service("open-webui") == "open-webui"
    with pytest.raises(ValueError):
        validate_profile("unknown")
    with pytest.raises(ValueError):
        validate_service("a/b")


def test_all_profile_flags_are_explicit() -> None:
    assert profiles_arguments(("core", "ai")) == ["--profile", "core", "--profile", "ai"]
