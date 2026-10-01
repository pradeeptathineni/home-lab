#!/usr/bin/env python3
"""compare complete local generation evidence without inventing a score"""

from __future__ import annotations

import json
from pathlib import Path

from benchmarks.ai.common import RESULTS, atomic_write_json, timestamp, timestamp_slug
from labctl import ai


def _latest(results: Path, prefix: str, model_id: str) -> tuple[Path, dict[str, object]]:
    matches = sorted(results.glob(f"{prefix}-{model_id}-*.json"))
    if not matches:
        raise RuntimeError(f"missing {prefix} evidence for {model_id}")
    path = matches[-1]
    payload = json.loads(path.read_text())
    if not isinstance(payload, dict):
        raise RuntimeError(f"invalid comparison input: {path}")
    return path, payload


def _median(payload: dict[str, object], name: str) -> float:
    aggregate = payload.get("aggregate")
    if not isinstance(aggregate, dict):
        raise RuntimeError(f"comparison input has no aggregate for {name}")
    metric = aggregate.get(name)
    if not isinstance(metric, dict) or not isinstance(metric.get("median"), (int, float)):
        raise RuntimeError(f"comparison input has no median for {name}")
    return float(metric["median"])


def build_comparison(repo: Path, results: Path = RESULTS) -> dict[str, object]:
    registry = ai.load_registry(repo)
    rows: list[dict[str, object]] = []
    for model in registry.models:
        if model.role != "generation":
            continue
        engine_path, engine = _latest(results, "ai-engine", model.id)
        api_path, api_result = _latest(results, "ai-api", model.id)
        eval_path, eval_result = _latest(results, "ai-eval", model.id)
        engine_aggregate = engine.get("aggregate")
        api_aggregate = api_result.get("aggregate")
        eval_aggregate = eval_result.get("aggregate")
        memory = api_result.get("memory")
        if not all(
            isinstance(value, dict)
            for value in (engine_aggregate, api_aggregate, eval_aggregate, memory)
        ):
            raise RuntimeError(f"incomplete comparison input for {model.id}")
        rows.append(
            {
                "model_id": model.id,
                "model_bytes": model.expected_bytes,
                "engine_prompt_tokens_per_second_median": _median(
                    engine, "prompt_tokens_per_second"
                ),
                "engine_generation_tokens_per_second_median": _median(
                    engine, "generation_tokens_per_second"
                ),
                "api_ttft_seconds_median": _median(api_result, "ttft_seconds"),
                "api_generation_tokens_per_second_median": _median(
                    api_result, "generation_tokens_per_second"
                ),
                "api_wall_time_seconds_median": _median(api_result, "wall_time_seconds"),
                "eval_passed": eval_aggregate["passed"],
                "eval_total": eval_aggregate["total"],
                "process_rss_bytes_peak": memory["process_rss_bytes_peak"],
                "api_failures": api_aggregate["failures"],
                "inputs": [engine_path.name, api_path.name, eval_path.name],
            }
        )
    if len(rows) < 2:
        raise RuntimeError("comparison requires evidence for at least two generation models")
    best_eval = max(int(row["eval_passed"]) for row in rows)
    eligible = [row for row in rows if int(row["eval_passed"]) == best_eval]
    selected = min(
        eligible,
        key=lambda row: (
            float(row["api_ttft_seconds_median"]),
            int(row["model_bytes"]),
            str(row["model_id"]),
        ),
    )
    return {
        "schema_version": "1",
        "benchmark": "ai-comparison",
        "timestamp": timestamp(),
        "decision_rule": (
            "highest deterministic pass count, then lowest median API TTFT, then smallest artifact"
        ),
        "measured_default": selected["model_id"],
        "models": rows,
        "caveats": [
            "the decision applies only to this host, runtime, and bounded workload",
            "no combined or universal model-quality score is calculated",
            "five performance samples support medians but not a robust p95",
        ],
    }


def main() -> int:
    repo = Path(__file__).resolve().parents[2]
    payload = build_comparison(repo)
    destination = RESULTS / f"ai-comparison-{timestamp_slug()}.json"
    atomic_write_json(destination, payload)
    print(destination)
    print(f"measured default: {payload['measured_default']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
