"""lima node lifecycle"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

from labctl.runner import CommandRunner

NODE_NAME = "home-lab"


def installed() -> bool:
    return shutil.which("limactl") is not None


def node_state() -> str:
    if not installed():
        return "missing"
    result = subprocess.run(
        ["limactl", "list", "--json"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return "unknown"
    for line in result.stdout.splitlines():
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if item.get("name") == NODE_NAME:
            return str(item.get("status", "unknown")).lower()
    return "absent"


def up(repo: Path, runner: CommandRunner) -> int:
    state = node_state()
    if state == "missing" and not runner.dry_run:
        raise RuntimeError("Lima is not installed; run 'brew install lima'")
    if state == "running":
        print("home-lab node is already running")
        return 0
    if state in {"absent", "missing"}:
        command = [
            "limactl",
            "start",
            "--tty=false",
            "--name",
            NODE_NAME,
            "--mount-only",
            str(repo),
            str(repo / "infra" / "lima" / "home-lab.yaml"),
        ]
    else:
        command = ["limactl", "start", "--tty=false", NODE_NAME]
    return runner.run(command).returncode


def down(runner: CommandRunner) -> int:
    return runner.run(["limactl", "stop", NODE_NAME]).returncode


def shell(runner: CommandRunner) -> int:
    return runner.run(["limactl", "shell", NODE_NAME]).returncode


def converge(repo: Path, runner: CommandRunner) -> int:
    ssh_config = Path.home() / ".lima" / NODE_NAME / "ssh.config"
    if not ssh_config.exists() and not runner.dry_run:
        raise RuntimeError("Lima SSH configuration is missing; start the node first")
    command = [
        str(Path(sys.executable).parent / "ansible-playbook"),
        "-i",
        str(repo / "infra" / "ansible" / "inventory" / "local.yml"),
        str(repo / "infra" / "ansible" / "playbooks" / "converge.yml"),
    ]
    env = {"ANSIBLE_SSH_ARGS": f"-F {ssh_config}"}
    return runner.run(command, cwd=repo / "infra" / "ansible", env=env).returncode
