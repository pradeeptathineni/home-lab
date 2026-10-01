"""actionable environment checks"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

from labctl.lima import node_state

REQUIRED = {
    "git": "install Xcode command line tools or Git",
    "python3": "install Python 3.12 or newer",
    "limactl": "run: brew install lima",
}
OPTIONAL = {
    "llama-server": "preferred local AI inference runtime",
    "ollama": "optional alternate local AI adapter",
    "tailscale": "needed only for private remote access",
    "restic": "needed only for backup commands",
}
SECRET_NAMES = (
    "HOMARR_SECRET_ENCRYPTION_KEY",
    "GRAFANA_ADMIN_PASSWORD",
    "PIHOLE_PASSWORD",
    "OPEN_WEBUI_ADMIN_PASSWORD",
    "WEBUI_SECRET_KEY",
    "PAPERLESS_SECRET_KEY",
)


def _version(command: list[str]) -> str | None:
    try:
        result = subprocess.run(command, check=False, capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        return None
    output = (result.stdout or result.stderr).splitlines()
    return output[0].strip() if output else None


def _guest_runtime_env() -> bool:
    try:
        result = subprocess.run(
            [
                "limactl",
                "shell",
                "home-lab",
                "--",
                "test",
                "-s",
                "/srv/home-lab/secrets/runtime.env",
            ],
            check=False,
            capture_output=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


def run(repo: Path) -> int:
    failures = 0
    print("Required tools")
    for tool, remedy in REQUIRED.items():
        location = shutil.which(tool)
        if location:
            print(f"  ok       {tool}: {location}")
        else:
            failures += 1
            print(f"  missing  {tool}: {remedy}")

    ansible = Path(sys.executable).parent / "ansible-playbook"
    if ansible.exists():
        print(f"  ok       ansible-playbook: {ansible}")
    else:
        failures += 1
        print("  missing  ansible-playbook: install this project with pip install -e '.[dev]'")

    print("Optional integrations")
    for tool, purpose in OPTIONAL.items():
        location = shutil.which(tool)
        state = location or f"not installed ({purpose})"
        print(f"  {'ok' if location else 'optional':8} {tool}: {state}")

    print("Runtime")
    configured = (repo / "compose.yaml").exists()
    print(f"  {'ok' if configured else 'missing':8} repository configuration")
    print(f"  info     Lima node: {node_state()}")
    compose = _version(["docker", "compose", "version"]) if shutil.which("docker") else None
    print(f"  {'ok' if compose else 'info':8} Compose: {compose or 'not available on host'}")

    print("Configuration")
    missing = [name for name in SECRET_NAMES if not os.environ.get(name)]
    if _guest_runtime_env():
        print("  ok       guest runtime env exists; values were not read")
    elif missing:
        print("  info     unset runtime secrets: " + ", ".join(missing))
        print("           load a private env file; secret values are never printed")
    else:
        print("  ok       required stateful profile variables are set")

    if failures:
        print(f"Doctor found {failures} required dependency issue(s).")
        return 1
    print("Doctor found no required dependency issues.")
    return 0
