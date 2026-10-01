#!/usr/bin/env python3
"""measure raw llama.cpp and OpenAI-compatible application behavior"""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from benchmarks.ai.common import (
    RESULTS,
    aggregate,
    atomic_write_json,
    command_output,
    host_available_memory_bytes,
    host_provenance,
    model_provenance,
    power_state,
    process_rss_bytes,
    timestamp,
    timestamp_slug,
)
from labctl import ai
from labctl.metrics import publish_to_guest, render_ai_metrics
from labctl.mlflow import log_evidence

THREADS = 8
CONTEXT = 2048
WARMUPS = 1
REPETITIONS = 5
PROMPT = 'Return exactly this JSON object with no markdown: {"answer":"blue"}'


def _json_payload(output: str) -> object:
    for marker in ("[", "{"):
        index = output.find(marker)
        if index >= 0:
            try:
                return json.loads(output[index:])
            except json.JSONDecodeError:
                continue
    raise RuntimeError("llama-bench did not emit parseable JSON")


def _bench_command(binary: str, model_path: Path) -> list[str]:
    help_text = command_output([binary, "--help"]) or ""
    output_flag = "--output-format" if "--output-format" in help_text else "--output"
    return [
        binary,
        "--model",
        str(model_path),
        "--threads",
        str(THREADS),
        "--n-prompt",
        "512",
        "--n-gen",
        "128",
        "--repetitions",
        str(REPETITIONS),
        output_flag,
        "json",
    ]


def _extract_engine_samples(raw: object) -> tuple[list[float], list[float], dict[str, object]]:
    entries = raw if isinstance(raw, list) else [raw]
    prompt_samples: list[float] = []
    generation_samples: list[float] = []
    metadata: dict[str, object] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        metadata.update(
            {
                key: entry.get(key)
                for key in ("build_commit", "backend", "cpu_info", "model_type")
                if entry.get(key) is not None
            }
        )
        samples = entry.get("samples_ts")
        if not isinstance(samples, list):
            average = entry.get("avg_ts")
            samples = [average] if isinstance(average, (int, float)) else []
        numeric = [float(value) for value in samples if isinstance(value, (int, float))]
        if int(entry.get("n_prompt") or 0) > 0 and int(entry.get("n_gen") or 0) == 0:
            prompt_samples.extend(numeric)
        if int(entry.get("n_gen") or 0) > 0:
            generation_samples.extend(numeric)
    if len(prompt_samples) < REPETITIONS or len(generation_samples) < REPETITIONS:
        raise RuntimeError("llama-bench output did not contain five prompt and generation samples")
    return prompt_samples, generation_samples, metadata


def run_engine(model: ai.Model, runtime: dict[str, object]) -> tuple[Path, dict[str, object]]:
    binary = ai.find_binary("llama-bench")
    if not binary:
        raise RuntimeError("llama-bench is not installed")
    command = _bench_command(binary, ai.model_path(model))
    started = time.perf_counter()
    result = subprocess.run(command, check=False, capture_output=True, text=True, timeout=900)
    duration = time.perf_counter() - started
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "llama-bench failed")
    raw = _json_payload(result.stdout)
    prompt_samples, generation_samples, metadata = _extract_engine_samples(raw)
    payload: dict[str, object] = {
        "schema_version": "1",
        "benchmark": "ai-engine",
        "timestamp": timestamp(),
        "host": host_provenance(),
        "runtime": runtime,
        "model": model_provenance(model),
        "configuration": {
            "threads": THREADS,
            "context_tokens": CONTEXT,
            "prompt_tokens": 512,
            "generation_tokens": 128,
            "repetitions": REPETITIONS,
        },
        "samples": {
            "prompt_tokens_per_second": prompt_samples,
            "generation_tokens_per_second": generation_samples,
        },
        "aggregate": {
            "prompt_tokens_per_second": aggregate(prompt_samples),
            "generation_tokens_per_second": aggregate(generation_samples),
        },
        "power": power_state(),
        "wall_time_seconds": duration,
        "runtime_metadata": metadata,
        "raw": raw,
        "caveats": [
            "llama-bench measures engine throughput, not chat latency",
            "five repetitions support raw/min/median/max but not a robust p95",
            "graphics/shared memory attribution is not reported",
        ],
    }
    destination = RESULTS / f"ai-engine-{model.id}-{timestamp_slug()}.json"
    atomic_write_json(destination, payload)
    return destination, payload


def _wait_for_server(process: subprocess.Popen[str], port: int, log_path: Path) -> None:
    for _ in range(120):
        if process.poll() is not None:
            raise RuntimeError(f"llama-server exited early; inspect {log_path}")
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=2) as response:
                if response.status == 200:
                    return
        except (OSError, urllib.error.URLError):
            pass
        time.sleep(1)
    raise RuntimeError(f"llama-server did not become healthy; inspect {log_path}")


def _stream_completion(port: int, model_id: str, warmup: bool, index: int) -> dict[str, object]:
    body = json.dumps(
        {
            "model": model_id,
            "messages": [{"role": "user", "content": PROMPT}],
            "temperature": 0,
            "seed": 42,
            "max_tokens": 48,
            "stream": True,
            "stream_options": {"include_usage": True},
            "chat_template_kwargs": {"enable_thinking": False},
        }
    ).encode()
    request = urllib.request.Request(
        f"http://127.0.0.1:{port}/v1/chat/completions",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    started = time.perf_counter()
    first_token: float | None = None
    content: list[str] = []
    usage: dict[str, object] = {}
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            for raw_line in response:
                line = raw_line.decode().strip()
                if not line.startswith("data: ") or line == "data: [DONE]":
                    continue
                chunk = json.loads(line[6:])
                if isinstance(chunk.get("usage"), dict):
                    usage = chunk["usage"]
                choices = chunk.get("choices") or []
                if choices:
                    token = choices[0].get("delta", {}).get("content")
                    if token:
                        if first_token is None:
                            first_token = time.perf_counter()
                        content.append(token)
    except (OSError, urllib.error.URLError, json.JSONDecodeError) as error:
        return {
            "index": index,
            "warmup": warmup,
            "success": False,
            "ttft_seconds": None,
            "wall_time_seconds": time.perf_counter() - started,
            "prompt_tokens": None,
            "output_tokens": None,
            "generation_tokens_per_second": None,
            "response": "",
            "exact_response": False,
            "error": str(error),
        }
    finished = time.perf_counter()
    prompt_tokens = usage.get("prompt_tokens")
    output_tokens = usage.get("completion_tokens")
    ttft = first_token - started if first_token else None
    generation_seconds = finished - first_token if first_token else None
    generation_rate = None
    if isinstance(output_tokens, int) and generation_seconds and generation_seconds > 0:
        generation_rate = output_tokens / generation_seconds
    response_text = "".join(content).strip()
    return {
        "index": index,
        "warmup": warmup,
        "success": True,
        "ttft_seconds": ttft,
        "wall_time_seconds": finished - started,
        "prompt_tokens": prompt_tokens,
        "output_tokens": output_tokens,
        "generation_tokens_per_second": generation_rate,
        "response": response_text,
        "exact_response": response_text == '{"answer":"blue"}',
        "error": None,
    }


def _metric_values(samples: list[dict[str, object]], key: str) -> list[float]:
    return [
        float(sample[key])
        for sample in samples
        if not sample["warmup"] and sample["success"] and sample[key] is not None
    ]


def run_api(
    repo: Path, model: ai.Model, runtime: dict[str, object]
) -> tuple[Path, dict[str, object]]:
    port = int(os.environ.get("HOME_LAB_AI_BENCHMARK_PORT", "18081"))
    command = ai.server_command(repo, model.id, port=port)
    runtime_dir = repo / ".runtime"
    runtime_dir.mkdir(exist_ok=True)
    log_path = runtime_dir / f"ai-benchmark-{model.id}.log"
    before_memory = host_available_memory_bytes()
    with log_path.open("w") as log:
        process = subprocess.Popen(
            command,
            stdout=log,
            stderr=subprocess.STDOUT,
            text=True,
            start_new_session=True,
        )
        try:
            _wait_for_server(process, port, log_path)
            samples: list[dict[str, object]] = []
            rss_samples: list[int] = []
            for index in range(WARMUPS + REPETITIONS):
                samples.append(_stream_completion(port, model.id, index < WARMUPS, index))
                rss = process_rss_bytes(process.pid)
                if rss is not None:
                    rss_samples.append(rss)
        finally:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=20)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait(timeout=5)
    measured = [sample for sample in samples if not sample["warmup"]]
    successes = sum(bool(sample["success"]) for sample in measured)
    metrics: dict[str, object] = {}
    for key in ("ttft_seconds", "wall_time_seconds", "generation_tokens_per_second"):
        values = _metric_values(samples, key)
        metrics[key] = aggregate(values) if values else None
    payload: dict[str, object] = {
        "schema_version": "2",
        "benchmark": "ai-api-generation",
        "timestamp": timestamp(),
        "host": host_provenance(),
        "runtime": runtime,
        "model": model_provenance(model),
        "configuration": {
            "threads": THREADS,
            "context_tokens": CONTEXT,
            "temperature": 0,
            "warmups": WARMUPS,
            "repetitions": REPETITIONS,
            "prompt": PROMPT,
        },
        "samples": samples,
        "aggregate": {
            "successes": successes,
            "failures": REPETITIONS - successes,
            **metrics,
        },
        "memory": {
            "model_bytes": model.expected_bytes,
            "process_rss_bytes_peak": max(rss_samples) if rss_samples else None,
            "host_available_before_bytes": before_memory,
            "host_available_after_bytes": host_available_memory_bytes(),
            "graphics_memory_bytes": None,
        },
        "power": power_state(),
        "server_log": str(log_path),
        "caveats": [
            "generation rate is measured from first streamed content to request completion",
            "five measured samples support raw/min/median/max but not a robust p95",
            "process RSS is sampled after requests and may miss a short-lived peak",
            "graphics/shared memory could not be attributed reliably and remains null",
        ],
    }
    destination = RESULTS / f"ai-api-{model.id}-{timestamp_slug()}.json"
    atomic_write_json(destination, payload)
    return destination, payload


def write_runtime_artifact(
    model: ai.Model,
    runtime: dict[str, object],
    engine: dict[str, object],
    api_result: dict[str, object],
) -> Path:
    payload = {
        "schema_version": "1",
        "artifact_kind": "runtime-metadata",
        "timestamp": timestamp(),
        "host": engine["host"],
        "runtime": runtime,
        "model": model_provenance(model),
        "engine_runtime_metadata": engine["runtime_metadata"],
        "engine_configuration": engine["configuration"],
        "api_configuration": api_result["configuration"],
        "power": api_result["power"],
    }
    destination = RESULTS / f"ai-runtime-{model.id}-{timestamp_slug()}.json"
    atomic_write_json(destination, payload)
    return destination


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo = Path(__file__).resolve().parents[2]
    model = ai.load_registry(repo).get(args.model)
    if model.role != "generation":
        print(f"{model.id} is not a generation model", file=sys.stderr)
        return 2
    state, _ = ai._installed_state(model)
    if state != "installed":
        print(f"not tested: model {model.id} is {state}", file=sys.stderr)
        return 3
    identity = ai.runtime_identity()
    if not identity["llama_cli"] or not ai.find_binary("llama-bench"):
        print("not tested: stable llama.cpp tools are not installed", file=sys.stderr)
        return 3
    runtime = {
        "name": "llama.cpp",
        "version": identity["llama_version"],
        "backend": identity["llama_devices"],
    }
    engine_path, engine = run_engine(model, runtime)
    print(engine_path)
    api_path, api_result = run_api(repo, model, runtime)
    print(api_path)
    runtime_path = write_runtime_artifact(model, runtime, engine, api_result)
    print(runtime_path)
    metrics_path = publish_to_guest(repo, render_ai_metrics(api_result))
    print(metrics_path)
    log_evidence(repo, "benchmark", [engine_path, api_path, runtime_path])
    aggregate_result = api_result["aggregate"]
    if not isinstance(aggregate_result, dict) or aggregate_result["successes"] != REPETITIONS:
        return 1
    return 0 if engine["aggregate"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
