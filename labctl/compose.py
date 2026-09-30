"""docker compose command construction"""

from __future__ import annotations

import os
import re
from pathlib import Path

PROFILES = (
    "core",
    "observability",
    "observability-full",
    "network-lab",
    "ai",
    "knowledge",
)
SERVICE_RE = re.compile(r"^[a-z0-9][a-z0-9_.-]*$")


def target() -> str:
    value = os.environ.get("LABCTL_TARGET", "lima")
    if value not in {"lima", "local"}:
        raise ValueError("LABCTL_TARGET must be 'lima' or 'local'")
    return value


def validate_profile(profile: str) -> str:
    if profile not in PROFILES:
        choices = ", ".join(PROFILES)
        raise ValueError(f"unknown profile '{profile}'; choose one of: {choices}")
    return profile


def validate_service(service: str) -> str:
    if not SERVICE_RE.fullmatch(service):
        raise ValueError("service names may contain lowercase letters, digits, '.', '_' and '-'")
    return service


def compose_command(
    repo: Path,
    arguments: list[str],
    *,
    execution_target: str | None = None,
) -> list[str]:
    selected = execution_target or target()
    if selected == "local":
        return [
            "docker",
            "compose",
            "--project-directory",
            str(repo),
            "--env-file",
            os.environ.get("LAB_ENV_FILE", str(repo / "config" / "example.env")),
            "-f",
            str(repo / "compose.yaml"),
            *arguments,
        ]

    # lima preserves the absolute path for an explicit read-only mount
    guest_repo = str(repo)
    guest_env = os.environ.get(
        "LAB_ENV_FILE_GUEST",
        "/srv/home-lab/secrets/runtime.env",
    )
    return [
        "limactl",
        "shell",
        "--workdir",
        guest_repo,
        "home-lab",
        "--",
        "docker",
        "compose",
        "--project-directory",
        guest_repo,
        "--env-file",
        guest_env,
        "-f",
        f"{guest_repo}/compose.yaml",
        *arguments,
    ]


def profiles_arguments(profiles: tuple[str, ...] = PROFILES) -> list[str]:
    arguments: list[str] = []
    for profile in profiles:
        arguments.extend(("--profile", profile))
    return arguments
