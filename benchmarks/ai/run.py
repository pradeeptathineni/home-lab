#!/usr/bin/env python3
"""measure one approved local ollama model"""

from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "benchmarks" / "results"


def _request(url: str, payload: dict[str, object] | None = None) -> object:
    body = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST" if body else "GET",
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        return json.load(response)


def main() -> int:
    if not shutil.which("ollama"):
        print("not tested: no approved local model (Ollama is not installed)")
        return 3

    model = os.environ.get("OLLAMA_MODEL")
    if not model:
        print("not tested: no approved local model (set OLLAMA_MODEL after approval)")
        return 3

    base_url = os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
    try:
        tags = _request(f"{base_url}/api/tags")
    except (OSError, urllib.error.URLError) as error:
        print(f"not tested: Ollama is unreachable: {error}")
        return 3

    installed = {entry["name"]: entry for entry in tags.get("models", [])}  # type: ignore[union-attr]
    if model not in installed:
        print(f"not tested: no approved local model ('{model}' is not installed; no pull)")
        return 3

    prompt = "Return exactly the lowercase word blue."
    temperature = 0.0
    started = time.perf_counter()
    response = _request(
        f"{base_url}/api/generate",
        {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": temperature, "num_ctx": 2048},
        },
    )
    wall_time_ms = (time.perf_counter() - started) * 1000
    prompt_count = int(response.get("prompt_eval_count", 0))  # type: ignore[union-attr]
    output_count = int(response.get("eval_count", 0))  # type: ignore[union-attr]
    prompt_duration = int(response.get("prompt_eval_duration", 0))  # type: ignore[union-attr]
    output_duration = int(response.get("eval_duration", 0))  # type: ignore[union-attr]
    model_info = installed[model]
    details = model_info.get("details", {})
    version = subprocess.run(
        ["ollama", "--version"], check=False, capture_output=True, text=True
    ).stdout.strip()

    result = {
        "schema_version": "1",
        "benchmark": "ai-generation",
        "timestamp": datetime.now(UTC).isoformat(),
        "host_class": "macbook-pro",
        "operating_environment": f"{platform.system()} {platform.machine()}",
        "runtime": "ollama",
        "runtime_version": version,
        "model": model,
        "model_digest": model_info.get("digest"),
        "quantization": details.get("quantization_level"),
        "context_tokens": 2048,
        "prompt_tokens": prompt_count,
        "output_tokens": output_count,
        "temperature": temperature,
        "repetitions": 1,
        "metrics": {
            "ttft_ms": None,
            "prompt_tokens_per_second": (
                prompt_count / (prompt_duration / 1_000_000_000) if prompt_duration else None
            ),
            "generation_tokens_per_second": (
                output_count / (output_duration / 1_000_000_000) if output_duration else None
            ),
            "wall_time_ms": wall_time_ms,
            "peak_memory_bytes": None,
        },
        "samples": [{"response": response.get("response"), "wall_time_ms": wall_time_ms}],
        "caveats": [
            "non-streaming API does not expose time to first token",
            "peak host and GPU memory were not measured",
            "one repetition is a smoke measurement, not a comparison study",
        ],
    }
    RESULTS.mkdir(parents=True, exist_ok=True)
    destination = RESULTS / f"ai-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}.json"
    destination.write_text(json.dumps(result, indent=2) + "\n")
    print(destination)
    return 0


if __name__ == "__main__":
    sys.exit(main())
