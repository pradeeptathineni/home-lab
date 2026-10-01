"""low-cardinality Prometheus summaries for local AI evidence"""

from __future__ import annotations

import os
import subprocess
from datetime import datetime
from pathlib import Path


def _escape(value: object) -> str:
    return str(value).replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')


def _labels(model: dict[str, object], benchmark: str) -> str:
    values = {
        "model": model["id"],
        "runtime": "llama.cpp",
        "quantization": model["quantization"],
        "benchmark": benchmark,
    }
    return ",".join(f'{key}="{_escape(value)}"' for key, value in values.items())


def _median(result: dict[str, object], key: str) -> float | None:
    aggregate = result.get("aggregate")
    if not isinstance(aggregate, dict):
        return None
    metric = aggregate.get(key)
    if not isinstance(metric, dict) or not isinstance(metric.get("median"), (int, float)):
        return None
    return float(metric["median"])


def render_ai_metrics(
    api_result: dict[str, object], eval_result: dict[str, object] | None = None
) -> str:
    model = api_result["model"]
    if not isinstance(model, dict):
        raise ValueError("AI result has no model provenance")
    labels = _labels(model, "api")
    families: list[tuple[str, str, float | int | None, str]] = [
        (
            "home_lab_ai_generation_tokens_per_second",
            "Median application generation throughput from measured streaming requests.",
            _median(api_result, "generation_tokens_per_second"),
            labels,
        ),
        (
            "home_lab_ai_ttft_seconds",
            "Median time to first streamed content token.",
            _median(api_result, "ttft_seconds"),
            labels,
        ),
        (
            "home_lab_ai_wall_time_seconds",
            "Median end-to-end application request wall time.",
            _median(api_result, "wall_time_seconds"),
            labels,
        ),
        (
            "home_lab_ai_model_bytes",
            "Verified local model artifact size.",
            model.get("bytes"),
            labels,
        ),
    ]
    memory = api_result.get("memory")
    if isinstance(memory, dict):
        families.append(
            (
                "home_lab_ai_process_rss_bytes",
                "Peak sampled resident set size of the measured model server.",
                memory.get("process_rss_bytes_peak"),
                labels,
            )
        )
    if eval_result:
        aggregate = eval_result.get("aggregate")
        eval_model = eval_result.get("model")
        if isinstance(aggregate, dict) and isinstance(eval_model, dict):
            families.append(
                (
                    "home_lab_ai_eval_pass_ratio",
                    "Deterministic local evaluation pass ratio.",
                    aggregate.get("pass_ratio"),
                    _labels(eval_model, "deterministic-eval"),
                )
            )
    timestamp = datetime.fromisoformat(str(api_result["timestamp"])).timestamp()
    families.append(
        (
            "home_lab_ai_last_success_timestamp_seconds",
            "Unix timestamp of the latest successful AI application benchmark.",
            timestamp,
            labels,
        )
    )
    lines: list[str] = []
    for name, help_text, value, metric_labels in families:
        if value is None:
            continue
        lines.extend((f"# HELP {name} {help_text}", f"# TYPE {name} gauge"))
        lines.append(f"{name}{{{metric_labels}}} {float(value):.9g}")
    return "\n".join(lines) + "\n"


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + f".{os.getpid()}.tmp")
    with temporary.open("w") as handle:
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def publish_to_guest(repo: Path, content: str) -> Path:
    local_path = repo / ".runtime" / "metrics" / "home_lab_ai.prom"
    atomic_write(local_path, content)
    guest_script = """
import os
import sys
import tempfile

destination = "/srv/home-lab/metrics/home_lab_ai.prom"
os.makedirs(os.path.dirname(destination), mode=0o755, exist_ok=True)
descriptor, temporary = tempfile.mkstemp(
    prefix="home_lab_ai.prom.", dir=os.path.dirname(destination)
)
try:
    with os.fdopen(descriptor, "w") as handle:
        handle.write(sys.stdin.read())
        handle.flush()
        os.fsync(handle.fileno())
    os.chmod(temporary, 0o644)
    os.replace(temporary, destination)
finally:
    if os.path.exists(temporary):
        os.unlink(temporary)
"""
    result = subprocess.run(
        ["limactl", "shell", "home-lab", "--", "sudo", "python3", "-c", guest_script],
        input=content,
        check=False,
        text=True,
    )
    if result.returncode:
        raise RuntimeError("failed to atomically publish AI metrics inside the primary Lima node")
    return local_path
