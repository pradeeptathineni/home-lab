"""bounded local AI model and runtime operations"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import shutil
import signal
import subprocess
import time
import tomllib
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from labctl.compose import compose_command
from labctl.runner import CommandRunner

MODEL_ID_RE = re.compile(r"^[a-z0-9][a-z0-9.-]*$")
SOURCE_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
ROLES = {"generation", "embedding"}
DEFAULT_MODEL_ROOT = Path.home() / "Library" / "Application Support" / "home-lab" / "models"
DEFAULT_LLAMA_BIN_DIR = (
    Path.home()
    / "Library"
    / "Application Support"
    / "home-lab"
    / "runtime"
    / "llama.cpp-v0.5.0"
    / "build"
    / "bin"
)
DEFAULT_PORT = 18080
ROUTE_SOCKET = "/srv/home-lab/ai-route/llama.sock"


@dataclass(frozen=True)
class Model:
    id: str
    role: str
    family: str
    source: str
    revision: str
    file: str
    quantization: str
    license: str
    expected_bytes: int
    sha256: str
    compatibility: str
    projector_required: bool

    @property
    def url(self) -> str:
        return f"https://huggingface.co/{self.source}/resolve/{self.revision}/{self.file}"


@dataclass(frozen=True)
class Registry:
    version: int
    download_budget_bytes: int
    models: tuple[Model, ...]

    def get(self, model_id: str) -> Model:
        for model in self.models:
            if model.id == model_id:
                return model
        raise ValueError(f"unknown model '{model_id}'; use 'labctl ai models'")


def load_registry(repo: Path) -> Registry:
    path = repo / "config" / "ai-models.toml"
    with path.open("rb") as handle:
        data = tomllib.load(handle)
    version = data.get("registry_version")
    budget = data.get("download_budget_bytes")
    if version != 1:
        raise ValueError("AI model registry_version must be 1")
    if not isinstance(budget, int) or budget <= 0:
        raise ValueError("AI model registry needs a positive download budget")

    models: list[Model] = []
    seen: set[str] = set()
    for raw in data.get("models", []):
        try:
            model = Model(**raw)
        except TypeError as error:
            raise ValueError(f"invalid AI model entry: {error}") from error
        if not MODEL_ID_RE.fullmatch(model.id) or model.id in seen:
            raise ValueError(f"invalid or duplicate model ID: {model.id}")
        if model.role not in ROLES:
            raise ValueError(f"invalid role for {model.id}: {model.role}")
        if not SOURCE_RE.fullmatch(model.source) or not model.license.strip():
            raise ValueError(f"model {model.id} needs a verified source and license")
        if Path(model.file).name != model.file or not model.file.endswith(".gguf"):
            raise ValueError(f"model {model.id} has an unsafe file name")
        if model.expected_bytes <= 0 or not SHA256_RE.fullmatch(model.sha256):
            raise ValueError(f"model {model.id} needs exact bytes and SHA-256")
        if model.projector_required:
            raise ValueError(f"model {model.id} requires an unregistered projector")
        seen.add(model.id)
        models.append(model)

    if not models:
        raise ValueError("AI model registry is empty")
    if sum(model.expected_bytes for model in models) > budget:
        raise ValueError("AI model registry exceeds its download budget")
    return Registry(version=version, download_budget_bytes=budget, models=tuple(models))


def model_root() -> Path:
    configured = os.environ.get("HOME_LAB_MODEL_ROOT")
    root = Path(configured).expanduser() if configured else DEFAULT_MODEL_ROOT
    if configured and not root.is_absolute():
        raise ValueError("HOME_LAB_MODEL_ROOT must be an absolute path")
    return root.resolve()


def model_path(model: Model, root: Path | None = None) -> Path:
    selected_root = (root or model_root()).resolve()
    destination = (selected_root / model.id / model.file).resolve()
    if not destination.is_relative_to(selected_root):
        raise ValueError("model path escaped HOME_LAB_MODEL_ROOT")
    return destination


def _digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _installed_state(model: Model, root: Path | None = None) -> tuple[str, str | None]:
    path = model_path(model, root)
    if not path.exists():
        return "missing", None
    if not path.is_file() or path.is_symlink():
        return "invalid", None
    if path.stat().st_size != model.expected_bytes:
        return "size-mismatch", None
    digest = _digest(path)
    return ("installed", digest) if digest == model.sha256 else ("digest-mismatch", digest)


def list_models(repo: Path) -> int:
    registry = load_registry(repo)
    print("ID\tROLE\tSTATE\tBYTES\tQUANTIZATION\tLICENSE\tDIGEST\tSOURCE")
    for model in registry.models:
        state, digest = _installed_state(model)
        print(
            "\t".join(
                (
                    model.id,
                    model.role,
                    state,
                    str(model.expected_bytes),
                    model.quantization,
                    model.license,
                    digest or "-",
                    f"{model.source}@{model.revision}",
                )
            )
        )
        print(f"  compatibility: {model.compatibility}")
    return 0


def fetch(repo: Path, runner: CommandRunner, model_id: str) -> int:
    registry = load_registry(repo)
    model = registry.get(model_id)
    if os.environ.get("HOME_LAB_ALLOW_MODEL_DOWNLOADS") == "0":
        raise RuntimeError("model downloads are disabled by HOME_LAB_ALLOW_MODEL_DOWNLOADS=0")

    state, digest = _installed_state(model)
    if state == "installed":
        print(f"reusing verified model: {model_path(model)} ({digest})")
        return 0
    if state != "missing":
        raise RuntimeError(f"refusing to replace {model.id}: existing artifact is {state}")

    registered_bytes = sum(entry.expected_bytes for entry in registry.models)
    if registered_bytes > registry.download_budget_bytes:
        raise RuntimeError("registered model bytes exceed the 7 GiB phase budget")

    destination = model_path(model)
    partial = destination.with_suffix(destination.suffix + ".partial")
    print("Proposed model download")
    print(f"  model:   {model.id} ({model.role})")
    print(f"  file:    {model.file}")
    print(f"  bytes:   {model.expected_bytes}")
    print(f"  license: {model.license}")
    print(f"  source:  {model.source}@{model.revision}")
    print(f"  sha256:  {model.sha256}")
    print(
        f"  registry total: {registered_bytes} / {registry.download_budget_bytes} authorized bytes"
    )
    if runner.dry_run:
        return runner.run(
            ["curl", "--fail", "--location", "--output", str(partial), model.url],
            check=False,
        ).returncode

    destination.parent.mkdir(parents=True, exist_ok=True)
    partial.unlink(missing_ok=True)
    result = runner.run(
        [
            "curl",
            "--fail",
            "--location",
            "--progress-bar",
            "--output",
            str(partial),
            model.url,
        ],
        check=False,
    )
    if result.returncode:
        return result.returncode
    actual_size = partial.stat().st_size
    actual_digest = _digest(partial)
    if actual_size != model.expected_bytes or actual_digest != model.sha256:
        partial.unlink(missing_ok=True)
        raise RuntimeError(
            f"download verification failed for {model.id}: "
            f"bytes={actual_size}, sha256={actual_digest}"
        )
    os.replace(partial, destination)
    print(f"installed verified model: {destination}")
    return 0


def _command_output(command: list[str]) -> str | None:
    try:
        result = subprocess.run(command, check=False, capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return None
    output = (result.stdout or result.stderr).strip()
    return output or None


def find_binary(name: str) -> str | None:
    discovered = shutil.which(name)
    if discovered:
        return discovered
    configured = os.environ.get("HOME_LAB_LLAMA_BIN_DIR")
    root = Path(configured).expanduser() if configured else DEFAULT_LLAMA_BIN_DIR
    if configured and not root.is_absolute():
        raise ValueError("HOME_LAB_LLAMA_BIN_DIR must be an absolute path")
    candidate = root / name
    return str(candidate) if candidate.is_file() and os.access(candidate, os.X_OK) else None


def _sysctl(name: str) -> str | None:
    return _command_output(["sysctl", "-n", name])


def runtime_identity() -> dict[str, object]:
    llama_cli = find_binary("llama-cli")
    llama_version = _command_output([llama_cli, "--version"]) if llama_cli else None
    devices = _command_output([llama_cli, "--list-devices"]) if llama_cli else None
    ollama = shutil.which("ollama")
    return {
        "llama_cli": llama_cli,
        "llama_version": llama_version,
        "llama_devices": devices,
        "ollama": ollama,
        "ollama_version": _command_output([ollama, "--version"]) if ollama else None,
    }


def _runtime_dir(repo: Path) -> Path:
    return repo / ".runtime"


def _state_path(repo: Path) -> Path:
    return _runtime_dir(repo) / "ai-server.json"


def _route_state_path(repo: Path) -> Path:
    return _runtime_dir(repo) / "ai-route.json"


def _read_json(path: Path) -> dict[str, object] | None:
    if not path.exists():
        return None
    try:
        value = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return {"invalid": True}
    return value if isinstance(value, dict) else {"invalid": True}


def _read_state(repo: Path) -> dict[str, object] | None:
    path = _state_path(repo)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return {"invalid": True}


def _process_command(pid: int) -> str | None:
    return _command_output(["ps", "-p", str(pid), "-o", "command="])


def _owned_process(state: dict[str, object]) -> bool:
    try:
        pid = int(state["pid"])
        expected_model = str(state["model_path"])
    except (KeyError, TypeError, ValueError):
        return False
    command = _process_command(pid)
    return bool(command and "llama-server" in command and expected_model in command)


def _owned_route(state: dict[str, object]) -> bool:
    try:
        pid = int(state["pid"])
        socket_path = str(state["socket"])
    except (KeyError, TypeError, ValueError):
        return False
    command = _process_command(pid)
    return bool(command and re.search(r"(^|/)ssh\s", command) and socket_path in command)


def inspect(repo: Path) -> int:
    root = model_root()
    cache_bytes = 0
    if root.exists():
        cache_bytes = sum(
            path.stat().st_size
            for path in root.rglob("*")
            if path.is_file() and not path.is_symlink()
        )
    state = _read_state(repo)
    identity = runtime_identity()
    report = {
        "architecture": platform.machine(),
        "macos_version": platform.mac_ver()[0],
        "cpu": _sysctl("machdep.cpu.brand_string"),
        "logical_cores": os.cpu_count(),
        "physical_cores": int(_sysctl("hw.physicalcpu") or 0) or None,
        "memory_bytes": int(_sysctl("hw.memsize") or 0) or None,
        **identity,
        "model_root": str(root),
        "model_cache_bytes": cache_bytes,
        "managed_server": (
            {**state, "owned_process_alive": _owned_process(state)} if state else "stopped"
        ),
    }
    print(json.dumps(report, indent=2))
    return 0


def server_command(repo: Path, model_id: str, port: int | None = None) -> list[str]:
    model = load_registry(repo).get(model_id)
    if model.role != "generation":
        raise ValueError(f"model {model_id} is not a generation model")
    path = model_path(model)
    state, _ = _installed_state(model)
    if state != "installed":
        raise RuntimeError(f"model {model_id} is {state}; run 'labctl ai fetch {model_id}'")
    server = find_binary("llama-server")
    if not server:
        raise RuntimeError("llama-server is not installed")
    selected_port = port or int(os.environ.get("HOME_LAB_AI_PORT", str(DEFAULT_PORT)))
    if not 1024 <= selected_port <= 65535:
        raise ValueError("HOME_LAB_AI_PORT must be between 1024 and 65535")
    threads = int(os.environ.get("HOME_LAB_AI_THREADS", "8"))
    if not 1 <= threads <= 64:
        raise ValueError("HOME_LAB_AI_THREADS must be between 1 and 64")
    return [
        server,
        "--model",
        str(path),
        "--alias",
        model.id,
        "--host",
        "127.0.0.1",
        "--port",
        str(selected_port),
        "--ctx-size",
        "2048",
        "--threads",
        str(threads),
        "--jinja",
        "--metrics",
        "--no-webui",
    ]


def _health(port: int) -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=2) as response:
            return response.status == 200
    except (OSError, urllib.error.URLError):
        return False


def serve(repo: Path, runner: CommandRunner, model_id: str) -> int:
    existing = _read_state(repo)
    if existing and _owned_process(existing):
        raise RuntimeError(
            f"managed AI server is already running for {existing.get('model_id', 'unknown')}"
        )
    if existing:
        raise RuntimeError("managed AI state exists but ownership cannot be proved; inspect it")

    command = server_command(repo, model_id)
    if runner.dry_run:
        return runner.run(command, check=False).returncode
    runtime_dir = _runtime_dir(repo)
    runtime_dir.mkdir(parents=True, exist_ok=True)
    log_path = runtime_dir / "ai-server.log"
    log = log_path.open("a")
    print(f"$ {' '.join(command)}", flush=True)
    process = subprocess.Popen(
        command,
        stdout=log,
        stderr=subprocess.STDOUT,
        text=True,
        start_new_session=True,
    )
    port = int(command[command.index("--port") + 1])
    model = load_registry(repo).get(model_id)
    state = {
        "pid": process.pid,
        "model_id": model_id,
        "model_path": str(model_path(model)),
        "port": port,
        "command": command,
        "started_at": datetime.now(UTC).isoformat(),
        "log": str(log_path),
    }
    _state_path(repo).write_text(json.dumps(state, indent=2) + "\n")
    for _ in range(90):
        if process.poll() is not None:
            _state_path(repo).unlink(missing_ok=True)
            raise RuntimeError(f"llama-server exited early; inspect {log_path}")
        if _health(port):
            print(f"managed AI server ready on http://127.0.0.1:{port}")
            return 0
        time.sleep(1)
    os.killpg(process.pid, signal.SIGTERM)
    _state_path(repo).unlink(missing_ok=True)
    raise RuntimeError(f"llama-server did not become healthy; inspect {log_path}")


def route_status(repo: Path) -> int:
    state = _read_json(_route_state_path(repo))
    report: object = "stopped"
    if state:
        report = {**state, "owned_process_alive": _owned_route(state)}
    print(json.dumps(report, indent=2))
    return 0


def route_start(repo: Path, runner: CommandRunner) -> int:
    route_state = _read_json(_route_state_path(repo))
    if route_state and _owned_route(route_state):
        raise RuntimeError("the private AI route is already active")
    if route_state:
        raise RuntimeError("AI route state exists but ownership cannot be proved; inspect it")
    server_state = _read_state(repo)
    if not server_state or not _owned_process(server_state):
        raise RuntimeError("start the managed loopback AI server before its private route")
    port = int(server_state["port"])
    prepare = [
        "limactl",
        "shell",
        "home-lab",
        "--",
        "sh",
        "-c",
        f"mkdir -p /srv/home-lab/ai-route && rm -f {ROUTE_SOCKET}",
    ]
    if runner.run(prepare, check=False).returncode:
        raise RuntimeError("failed to prepare the private guest socket")
    ssh_config = Path.home() / ".lima" / "home-lab" / "ssh.config"
    command = [
        "ssh",
        "-F",
        str(ssh_config),
        "-S",
        "none",
        "-N",
        "-T",
        "-o",
        "ControlMaster=no",
        "-o",
        "ExitOnForwardFailure=yes",
        "-o",
        "ServerAliveInterval=15",
        "-o",
        "ServerAliveCountMax=3",
        "-R",
        f"{ROUTE_SOCKET}:127.0.0.1:{port}",
        "lima-home-lab",
    ]
    if runner.dry_run:
        return runner.run(command, check=False).returncode
    runtime_dir = _runtime_dir(repo)
    runtime_dir.mkdir(parents=True, exist_ok=True)
    log_path = runtime_dir / "ai-route.log"
    with log_path.open("a") as log:
        process = subprocess.Popen(
            command,
            stdout=log,
            stderr=subprocess.STDOUT,
            text=True,
            start_new_session=True,
        )
    state = {
        "pid": process.pid,
        "socket": ROUTE_SOCKET,
        "host": "127.0.0.1",
        "host_port": port,
        "model_id": server_state["model_id"],
        "server_pid": server_state["pid"],
        "started_at": datetime.now(UTC).isoformat(),
        "log": str(log_path),
    }
    _route_state_path(repo).write_text(json.dumps(state, indent=2) + "\n")
    socket_check = ["limactl", "shell", "home-lab", "--", "test", "-S", ROUTE_SOCKET]
    for _ in range(30):
        if process.poll() is not None:
            _route_state_path(repo).unlink(missing_ok=True)
            raise RuntimeError(f"private AI route exited early; inspect {log_path}")
        if subprocess.run(socket_check, check=False).returncode == 0:
            break
        time.sleep(1)
    else:
        os.killpg(process.pid, signal.SIGTERM)
        _route_state_path(repo).unlink(missing_ok=True)
        raise RuntimeError(f"private AI route did not create its socket; inspect {log_path}")
    permission_result = subprocess.run(
        ["limactl", "shell", "home-lab", "--", "chmod", "0660", ROUTE_SOCKET],
        check=False,
    )
    if permission_result.returncode:
        route_stop(repo, runner)
        raise RuntimeError("failed to apply the private route socket permissions")
    result = runner.run(
        compose_command(repo, ["--profile", "ai", "up", "-d", "ai-loopback-bridge"]),
        check=False,
    )
    if result.returncode:
        route_stop(repo, runner)
        raise RuntimeError("failed to start the internal AI socket bridge")
    print("private AI route ready: host loopback -> SSH Unix socket -> internal AI network")
    return 0


def route_stop(repo: Path, runner: CommandRunner) -> int:
    state = _read_json(_route_state_path(repo))
    if not state:
        print("private AI route is already stopped")
        return 0
    if not _owned_route(state):
        raise RuntimeError("refusing to stop an AI route whose ownership cannot be proved")
    pid = int(state["pid"])
    if runner.dry_run:
        return runner.run(["kill", "-TERM", str(pid)], check=False).returncode
    os.killpg(pid, signal.SIGTERM)
    for _ in range(50):
        if _process_command(pid) is None:
            _route_state_path(repo).unlink(missing_ok=True)
            subprocess.run(
                ["limactl", "shell", "home-lab", "--", "rm", "-f", ROUTE_SOCKET],
                check=False,
            )
            print("private AI route stopped")
            return 0
        time.sleep(0.1)
    raise RuntimeError("private AI route did not stop after SIGTERM")


def configure_open_webui(repo: Path, runner: CommandRunner) -> int:
    state = _read_json(_route_state_path(repo))
    if not state or not _owned_route(state):
        raise RuntimeError("start the owned private AI route before configuring Open WebUI")
    command = compose_command(
        repo,
        [
            "--profile",
            "ai",
            "exec",
            "-T",
            "open-webui",
            "python",
            "/opt/home-lab/configure-open-webui.py",
            "--model",
            str(state["model_id"]),
        ],
    )
    return runner.run(command, check=False).returncode


def stop(repo: Path, runner: CommandRunner) -> int:
    if _read_json(_route_state_path(repo)):
        route_stop(repo, runner)
    state = _read_state(repo)
    if not state:
        print("managed AI server is already stopped")
        return 0
    if not _owned_process(state):
        raise RuntimeError("refusing to stop a process whose managed ownership cannot be proved")
    pid = int(state["pid"])
    if runner.dry_run:
        return runner.run(["kill", "-TERM", str(pid)], check=False).returncode
    os.killpg(pid, signal.SIGTERM)
    for _ in range(50):
        if _process_command(pid) is None:
            _state_path(repo).unlink(missing_ok=True)
            print("managed AI server stopped")
            return 0
        time.sleep(0.1)
    raise RuntimeError("managed AI server did not stop after SIGTERM")
