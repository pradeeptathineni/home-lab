"""disposable Lima experiment node lifecycle"""

from __future__ import annotations

import json
import socket
import subprocess
import sys
import time
from pathlib import Path

from benchmarks.ai.common import atomic_write_json, timestamp_slug
from labctl.lima import NODE_NAME as PRIMARY_NODE
from labctl.runner import CommandRunner

NODE_NAME = "home-lab-sandbox"


def _list() -> list[dict[str, object]]:
    result = subprocess.run(
        ["limactl", "list", "--json"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode:
        return []
    items: list[dict[str, object]] = []
    for line in result.stdout.splitlines():
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            items.append(value)
    return items


def node_record() -> dict[str, object] | None:
    return next((item for item in _list() if item.get("name") == NODE_NAME), None)


def state() -> str:
    item = node_record()
    return str(item.get("status", "unknown")).lower() if item else "absent"


def create(repo: Path, runner: CommandRunner) -> int:
    current = state()
    if current != "absent":
        raise RuntimeError(f"{NODE_NAME} already exists with state {current}")
    command = [
        "limactl",
        "start",
        "--tty=false",
        "--name",
        NODE_NAME,
        str(repo / "infra" / "lima" / "sandbox.yaml"),
    ]
    return runner.run(command).returncode


def start(runner: CommandRunner) -> int:
    current = state()
    if current == "running":
        print(f"{NODE_NAME} is already running")
        return 0
    if current == "absent" and not runner.dry_run:
        raise RuntimeError("sandbox is absent; run 'labctl sandbox create'")
    return runner.run(["limactl", "start", "--tty=false", NODE_NAME]).returncode


def stop(runner: CommandRunner) -> int:
    current = state()
    if current == "absent":
        print(f"{NODE_NAME} is absent")
        return 0
    if current == "stopped":
        print(f"{NODE_NAME} is already stopped")
        return 0
    return runner.run(["limactl", "stop", NODE_NAME]).returncode


def shell(runner: CommandRunner) -> int:
    return runner.run(["limactl", "shell", NODE_NAME]).returncode


def destroy_command() -> list[str]:
    if NODE_NAME == PRIMARY_NODE:
        raise RuntimeError("sandbox node name must never equal the primary node")
    return ["limactl", "delete", NODE_NAME]


def destroy(runner: CommandRunner, approved: bool) -> int:
    current = state()
    if current == "absent":
        print(f"{NODE_NAME} is already absent")
        return 0
    if not approved:
        if not sys.stdin.isatty():
            raise RuntimeError("sandbox destroy requires --yes or an interactive terminal")
        answer = input(f"Destroy disposable VM {NODE_NAME}? Type yes: ")
        if answer != "yes":
            print("sandbox destroy cancelled")
            return 1
    if current == "running":
        result = runner.run(["limactl", "stop", NODE_NAME], check=False)
        if result.returncode:
            return result.returncode
    return runner.run(destroy_command()).returncode


VERIFY_SCRIPT = r"""
import json
import os
import socket

def resolve(name):
    try:
        return {"resolved": True, "address": socket.gethostbyname(name)}
    except OSError as error:
        return {"resolved": False, "error": str(error)}

def connect(name, port):
    try:
        with socket.create_connection((name, port), timeout=3):
            return {"reachable": True}
    except OSError as error:
        return {"reachable": False, "error": str(error)}

mounts = open("/proc/mounts").read().splitlines()
host_mounts = [
    line for line in mounts
    if ("virtiofs" in line or " 9p " in line) and not line.split()[1].startswith("/run/lima")
]
report = {
    "dns": resolve("example.com"),
    "internet_egress": connect("example.com", 443),
    "primary_vm_dns": resolve("lima-home-lab.internal"),
    "primary_vm_caddy": connect("lima-home-lab.internal", 8080),
    "mac_host_dns": resolve("host.lima.internal"),
    "mac_host_owned_port": connect("host.lima.internal", 8080),
    "host_mounts": host_mounts,
    "docker_socket_present": os.path.exists("/var/run/docker.sock"),
    "primary_state_present": os.path.exists("/srv/home-lab"),
}
print(json.dumps(report))
"""


def verify(repo: Path) -> int:
    item = node_record()
    if not item or str(item.get("status", "")).lower() != "running":
        raise RuntimeError("sandbox must be running before verification")
    command = ["limactl", "shell", NODE_NAME, "--", "python3", "-c", VERIFY_SCRIPT]
    result = subprocess.run(command, check=False, capture_output=True, text=True, timeout=60)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "sandbox verification failed")
    guest = json.loads(result.stdout)
    config = item.get("config") if isinstance(item.get("config"), dict) else {}
    inbound_forwarding = _probe_dynamic_forwarding()
    report = {
        "node": NODE_NAME,
        "state": "running",
        "configured_mounts": config.get("mounts", []),
        "configured_port_forwards": config.get("portForwards", []),
        "network": config.get("networks", []),
        "plain_mode": config.get("plain", False),
        "inbound_host_forwarding": inbound_forwarding,
        **guest,
    }
    failures = []
    if report["configured_mounts"] or report["configured_port_forwards"]:
        failures.append("sandbox has a configured host mount or port forward")
    if not report["plain_mode"] or report["inbound_host_forwarding"]:
        failures.append("sandbox dynamic host forwarding is not disabled")
    if report["host_mounts"] or report["docker_socket_present"] or report["primary_state_present"]:
        failures.append("sandbox inherited prohibited host or primary-lab state")
    if report["primary_vm_dns"].get("resolved") or report["primary_vm_caddy"].get("reachable"):
        failures.append("sandbox can resolve or reach the primary Lima node")
    if not report["dns"].get("resolved") or not report["internet_egress"].get("reachable"):
        failures.append("sandbox lacks the DNS or internet egress required by this experiment")
    report["boundary_failures"] = failures
    print(json.dumps(report, indent=2))
    planning = repo.parent / "home-lab-planning" / "outputs" / "02" / "sandbox-network.json"
    atomic_write_json(planning, report)
    return 1 if failures else 0


def _probe_dynamic_forwarding() -> bool:
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    listener_code = (
        "import socket,time;"
        "s=socket.socket();s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1);"
        f"s.bind(('0.0.0.0',{port}));s.listen();time.sleep(15)"
    )
    process = subprocess.Popen(
        ["limactl", "shell", NODE_NAME, "--", "python3", "-c", listener_code],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        ready = False
        for _ in range(20):
            check = subprocess.run(
                [
                    "limactl",
                    "shell",
                    NODE_NAME,
                    "--",
                    "python3",
                    "-c",
                    (f"import socket;s=socket.create_connection(('127.0.0.1',{port}),2);s.close()"),
                ],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            if check.returncode == 0:
                ready = True
                break
            time.sleep(0.25)
        if not ready:
            raise RuntimeError("sandbox forwarding probe listener did not become ready")
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=2):
                return True
        except OSError:
            return False
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=2)


def _ensure_running(repo: Path) -> str:
    initial = state()
    runner = CommandRunner()
    if initial == "absent" and create(repo, runner):
        raise RuntimeError("failed to create sandbox")
    if initial == "stopped" and start(runner):
        raise RuntimeError("failed to start sandbox")
    return initial


def network_fault_experiment(repo: Path) -> int:
    initial = _ensure_running(repo)
    script = (repo / "benchmarks" / "fault" / "run.py").read_text()
    lima_version = subprocess.run(
        ["limactl", "--version"], check=False, capture_output=True, text=True
    ).stdout.strip()
    command = ["limactl", "shell", NODE_NAME, "--", "python3", "-", lima_version]
    result = subprocess.run(
        command,
        input=script,
        check=False,
        capture_output=True,
        text=True,
        timeout=1200,
    )
    if result.returncode:
        print(result.stderr, file=sys.stderr)
        print(f"sandbox left running for debugging: {NODE_NAME}", file=sys.stderr)
        return result.returncode
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise RuntimeError(f"fault experiment returned invalid JSON: {error}") from error
    destination = repo / "benchmarks" / "results" / f"fault-http-{timestamp_slug()}.json"
    atomic_write_json(destination, payload)
    print(destination)
    if initial != "running":
        stop(CommandRunner())
    return 0
