#!/usr/bin/env python3
"""log local benchmark files to the existing MLflow tracking service"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import mlflow


def _median(result: dict[str, object], name: str) -> float | None:
    aggregate = result.get("aggregate")
    if not isinstance(aggregate, dict):
        return None
    metric = aggregate.get(name)
    if not isinstance(metric, dict):
        return None
    value = metric.get("median")
    return float(value) if isinstance(value, (int, float)) else None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--kind", choices=("benchmark", "eval", "retrieval"), required=True)
    parser.add_argument("artifacts", nargs="+")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    paths = [Path(value) for value in args.artifacts]
    loaded = [json.loads(path.read_text()) for path in paths if path.suffix == ".json"]
    documents = [document for document in loaded if isinstance(document, dict)]
    evidence = next(
        (
            document
            for document in documents
            if isinstance(document, dict) and isinstance(document.get("model"), dict)
        ),
        None,
    )
    if evidence is None:
        raise ValueError("no evidence artifact contained model provenance")
    model = evidence["model"]
    runtime = evidence.get("runtime", {})
    configuration = evidence.get("configuration", {})
    mlflow.set_tracking_uri("http://127.0.0.1:5000")
    mlflow.set_experiment("home-lab-ai-evidence")
    with mlflow.start_run(run_name=f"{args.kind}-{model['id']}") as run:
        mlflow.log_params(
            {
                "model_id": model["id"],
                "model_digest": model["digest"],
                "quantization": model["quantization"],
                "runtime": runtime.get("name", "llama.cpp"),
                "runtime_version": str(runtime.get("version", "unknown"))[:500],
                "backend": str(runtime.get("backend", "unknown"))[:500],
                "context": configuration.get("context_tokens", "unknown"),
                "threads": configuration.get("threads", "unknown"),
                "temperature": configuration.get("temperature", "unknown"),
                "benchmark_revision": "2",
                "host_class": evidence.get("host", {}).get("class", "unknown"),
            }
        )
        for document in documents:
            benchmark = document.get("benchmark")
            metrics: dict[str, float] = {}
            if benchmark == "ai-engine":
                generation = _median(document, "generation_tokens_per_second")
                prompt = _median(document, "prompt_tokens_per_second")
                if generation is not None:
                    metrics["engine_generation_tokens_per_second_median"] = generation
                if prompt is not None:
                    metrics["engine_prompt_tokens_per_second_median"] = prompt
            if benchmark == "ai-api-generation":
                for source, destination in (
                    ("generation_tokens_per_second", "generation_tokens_per_second_median"),
                    ("ttft_seconds", "ttft_seconds_median"),
                    ("wall_time_seconds", "wall_time_seconds_median"),
                ):
                    value = _median(document, source)
                    if value is not None:
                        metrics[destination] = value
                rss = document.get("memory", {}).get("process_rss_bytes_peak")
                if isinstance(rss, (int, float)):
                    metrics["process_rss_bytes_peak"] = float(rss)
            if benchmark == "ai-deterministic-eval":
                aggregate = document["aggregate"]
                metrics.update(
                    {
                        "eval_passed": float(aggregate["passed"]),
                        "eval_total": float(aggregate["total"]),
                        "eval_pass_ratio": float(aggregate["pass_ratio"]),
                    }
                )
            if benchmark == "ai-retrieval":
                aggregate = document["aggregate"]
                metrics.update(
                    {
                        "retrieval_hit_at_1": float(aggregate["hit_at_1"]),
                        "retrieval_hit_at_3": float(aggregate["hit_at_3"]),
                        "retrieval_mrr": float(aggregate["mrr"]),
                    }
                )
            if metrics:
                mlflow.log_metrics(metrics)
        for path in paths:
            mlflow.log_artifact(str(path), artifact_path="evidence")
        print(run.info.run_id)


if __name__ == "__main__":
    main()
