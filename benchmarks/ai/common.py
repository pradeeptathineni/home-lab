"""shared deterministic AI evidence helpers"""

from __future__ import annotations

import json
import os
import platform
import statistics
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from labctl.ai import Model

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "benchmarks" / "results"


def timestamp() -> str:
    return datetime.now(UTC).isoformat()


def timestamp_slug() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def aggregate(values: list[float]) -> dict[str, float | list[float]]:
    if not values:
        raise ValueError("cannot aggregate an empty sample")
    return {
        "raw": values,
        "min": min(values),
        "median": statistics.median(values),
        "max": max(values),
    }


def atomic_write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + f".{os.getpid()}.tmp")
    with temporary.open("w") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def model_provenance(model: Model) -> dict[str, object]:
    return {
        "id": model.id,
        "family": model.family,
        "source": model.source,
        "revision": model.revision,
        "digest": model.sha256,
        "quantization": model.quantization,
        "bytes": model.expected_bytes,
    }


def host_provenance() -> dict[str, object]:
    return {
        "class": "intel-macbook-pro",
        "os": platform.system(),
        "os_version": platform.mac_ver()[0],
        "architecture": platform.machine(),
    }


def command_output(command: list[str], timeout: int = 15) -> str | None:
    try:
        result = subprocess.run(
            command, check=False, capture_output=True, text=True, timeout=timeout
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    output = (result.stdout or result.stderr).strip()
    return output or None


def power_state() -> dict[str, object]:
    output = command_output(["pmset", "-g", "batt"])
    if not output:
        return {"source": "unknown", "battery_percent": None}
    source = "ac" if "AC Power" in output else "battery" if "Battery Power" in output else "unknown"
    percent = None
    for token in output.replace(";", " ").split():
        if token.endswith("%") and token[:-1].isdigit():
            percent = int(token[:-1])
            break
    return {"source": source, "battery_percent": percent}


def host_available_memory_bytes() -> int | None:
    output = command_output(["vm_stat"])
    if not output:
        return None
    page_size = 4096
    available_pages = 0
    for line in output.splitlines():
        if "page size of" in line:
            words = line.split()
            page_size = int(words[words.index("of") + 1])
        if line.startswith(("Pages free:", "Pages inactive:", "Pages speculative:")):
            available_pages += int(line.split(":", maxsplit=1)[1].strip().rstrip("."))
    return available_pages * page_size


def process_rss_bytes(pid: int) -> int | None:
    output = command_output(["ps", "-p", str(pid), "-o", "rss="])
    if not output:
        return None
    try:
        return int(output.splitlines()[0].strip()) * 1024
    except ValueError:
        return None
