#!/usr/bin/env python3
"""measure explicit queries through the dns lab client"""

from __future__ import annotations

import json
import os
import statistics
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from labctl.compose import compose_command

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "benchmarks" / "results"


def _query(domain: str, repetitions: int) -> list[dict[str, object]]:
    command = compose_command(
        ROOT,
        [
            "--profile",
            "network-lab",
            "exec",
            "-T",
            "dns-test-client",
            "python",
            "/probe.py",
            "--server",
            "pihole",
            "--domain",
            domain,
            "--repetitions",
            str(repetitions),
            "--json",
        ],
    )
    result = subprocess.run(command, check=False, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"DNS probe failed for {domain}")
    return json.loads(result.stdout)


def main() -> int:
    repetitions = int(os.environ.get("DNS_BENCHMARK_REPETITIONS", "5"))
    if repetitions < 2 or repetitions > 50:
        print("DNS_BENCHMARK_REPETITIONS must be between 2 and 50", file=sys.stderr)
        return 2
    domains = {
        "allowed": os.environ.get("DNS_ALLOWED_DOMAIN", "example.com"),
        "block-test": os.environ.get("DNS_BLOCK_TEST_DOMAIN", "doubleclick.net"),
    }
    queries: list[dict[str, object]] = []
    for domain_class, domain in domains.items():
        for index, measurement in enumerate(_query(domain, repetitions)):
            queries.append(
                {
                    "domain_class": domain_class,
                    "phase": "cold" if index == 0 else "warm",
                    **measurement,
                }
            )

    warm_times = [float(item["wall_time_ms"]) for item in queries if item["phase"] == "warm"]
    result = {
        "schema_version": "1",
        "benchmark": "dns",
        "timestamp": datetime.now(UTC).isoformat(),
        "repetitions": repetitions,
        "queries": queries,
        "aggregate_warm_median_ms": statistics.median(warm_times),
        "caveats": [
            "the first lookup is labeled cold but upstream and Pi-hole caches were not "
            "forcibly cleared",
            "the block-test result depends on the active Pi-hole lists",
            "wall time covers the UDP request inside the isolated client",
        ],
    }
    RESULTS.mkdir(parents=True, exist_ok=True)
    destination = RESULTS / f"dns-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}.json"
    destination.write_text(json.dumps(result, indent=2) + "\n")
    print(destination)
    return 0


if __name__ == "__main__":
    sys.exit(main())
