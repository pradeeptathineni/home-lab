#!/usr/bin/env python3
"""run a bounded http latency probe"""

from __future__ import annotations

import json
import os
import statistics
import sys
import time
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "benchmarks" / "results"


def main() -> int:
    repetitions = int(os.environ.get("NETWORK_BENCHMARK_REPETITIONS", "5"))
    if repetitions < 2 or repetitions > 20:
        print("NETWORK_BENCHMARK_REPETITIONS must be between 2 and 20", file=sys.stderr)
        return 2
    url = os.environ.get("NETWORK_BENCHMARK_URL", "http://127.0.0.1:8080/healthz")
    samples: list[float] = []
    for _ in range(repetitions):
        started = time.perf_counter()
        with urllib.request.urlopen(url, timeout=10) as response:
            response.read(1)
        samples.append((time.perf_counter() - started) * 1000)

    result = {
        "schema_version": "1",
        "benchmark": "network-http",
        "timestamp": datetime.now(UTC).isoformat(),
        "method": "HTTP GET",
        "target": url,
        "repetitions": repetitions,
        "samples": samples,
        "aggregate": {
            "min_ms": min(samples),
            "median_ms": statistics.median(samples),
            "max_ms": max(samples),
        },
        "caveats": [
            "this is application-level HTTP latency, not packet loss or bandwidth",
            "the default target is the owned Caddy health route forwarded from Lima",
            "endpoint load and connection reuse affect the result",
        ],
    }
    RESULTS.mkdir(parents=True, exist_ok=True)
    destination = RESULTS / f"network-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}.json"
    destination.write_text(json.dumps(result, indent=2) + "\n")
    print(destination)
    return 0


if __name__ == "__main__":
    sys.exit(main())
