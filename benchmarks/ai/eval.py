#!/usr/bin/env python3
"""run deterministic local behavioral evaluation without a model judge"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

from benchmarks.ai.common import (
    RESULTS,
    atomic_write_json,
    host_provenance,
    model_provenance,
    timestamp,
    timestamp_slug,
)
from benchmarks.ai.run import THREADS, _wait_for_server
from labctl import ai
from labctl.metrics import publish_to_guest, render_ai_metrics
from labctl.mlflow import log_evidence

SYSTEM_PROMPT = (
    "Return only one valid JSON object with no markdown or commentary. "
    "Use exactly the requested fields. For code tasks put the complete Python "
    "source in a code field."
)


def _extract_object(text: str) -> dict[str, object] | None:
    decoder = json.JSONDecoder()
    candidates: list[dict[str, object]] = []
    for index, character in enumerate(text):
        if character != "{":
            continue
        try:
            value, _ = decoder.raw_decode(text[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            candidates.append(value)
    return candidates[-1] if candidates else None


ALLOWED_AST = {
    ast.Module,
    ast.FunctionDef,
    ast.arguments,
    ast.arg,
    ast.Return,
    ast.BinOp,
    ast.Name,
    ast.Load,
    ast.Add,
    ast.Mod,
    ast.Compare,
    ast.Eq,
    ast.Constant,
}


def _executable_python_check(
    payload: dict[str, object], function: str, tests: list[list[object]]
) -> tuple[bool, str]:
    code = payload.get("code")
    if not isinstance(code, str):
        return False, "response did not contain a code string"
    try:
        tree = ast.parse(code)
    except SyntaxError as error:
        return False, f"invalid Python: {error.msg}"
    if any(type(node) not in ALLOWED_AST for node in ast.walk(tree)):
        return False, "generated code used syntax outside the safe executable subset"
    functions = [node.name for node in tree.body if isinstance(node, ast.FunctionDef)]
    if functions != [function]:
        return False, f"expected only function {function}"
    assertions = "\n".join(
        f"assert {function}({input_value!r}) == {expected!r}" for input_value, expected in tests
    )
    with tempfile.TemporaryDirectory(prefix="home-lab-eval-") as directory:
        script = Path(directory) / "candidate.py"
        script.write_text(f"{code}\n{assertions}\n")
        result = subprocess.run(
            [sys.executable, "-I", str(script)],
            check=False,
            capture_output=True,
            text=True,
            timeout=2,
        )
    if result.returncode:
        return False, (result.stderr or "executable assertions failed").strip()
    return True, "safe-subset executable tests passed"


def _evaluate(case: dict[str, object], payload: dict[str, object] | None) -> tuple[bool, str]:
    if payload is None:
        return False, "no valid JSON object was found"
    if case.get("validator") == "python-function":
        return _executable_python_check(
            payload,
            str(case["function"]),
            case["tests"],  # type: ignore[arg-type]
        )
    expected = case.get("expected")
    return (
        payload == expected,
        "exact structured match" if payload == expected else "value mismatch",
    )


def _completion(port: int, model_id: str, request_text: str) -> tuple[str, float, str | None]:
    body = json.dumps(
        {
            "model": model_id,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": request_text},
            ],
            "temperature": 0,
            "seed": 42,
            "max_tokens": 256,
            "stream": False,
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
    try:
        with urllib.request.urlopen(request, timeout=240) as response:
            result = json.load(response)
        text = str(result["choices"][0]["message"].get("content") or "")
        return text, time.perf_counter() - started, None
    except (OSError, KeyError, IndexError, TypeError, urllib.error.URLError) as error:
        return "", time.perf_counter() - started, str(error)


def _run_promptfoo(repo: Path, model_id: str, port: int) -> Path:
    destination = RESULTS / f"promptfoo-{model_id}-{timestamp_slug()}.json"
    log_path = repo / ".runtime" / f"promptfoo-{model_id}.log"
    environment = os.environ.copy()
    environment.update(
        {
            "AI_MODEL_ID": model_id,
            "LLAMA_BASE_URL": f"http://127.0.0.1:{port}/v1",
            "PROMPTFOO_DISABLE_TELEMETRY": "true",
        }
    )
    command = [
        "npx",
        "--yes",
        "promptfoo@0.123.1",
        "eval",
        "--config",
        str(repo / "services" / "ai" / "promptfoo" / "promptfooconfig.yaml"),
        "--output",
        str(destination),
        "--no-cache",
    ]
    with log_path.open("w") as log:
        subprocess.run(
            command,
            cwd=repo / "services" / "ai" / "promptfoo",
            env=environment,
            stdout=log,
            stderr=subprocess.STDOUT,
            check=False,
            text=True,
            timeout=1200,
        )
    # Promptfoo returns non-zero when assertions fail. That is measured model
    # behavior, not an execution failure; a parseable result file is the
    # postcondition for this independent evaluation pass.
    if not destination.exists():
        raise RuntimeError(f"promptfoo evaluation failed; inspect {log_path}")
    try:
        json.loads(destination.read_text())
    except json.JSONDecodeError as error:
        raise RuntimeError(f"promptfoo emitted invalid JSON; inspect {log_path}") from error
    return destination


def _write_evaluation_config(repo: Path, model: ai.Model, cases: list[dict[str, object]]) -> Path:
    promptfoo_root = repo / "services" / "ai" / "promptfoo"
    promptfoo_config = promptfoo_root / "promptfooconfig.yaml"
    promptfoo_dataset = promptfoo_root / "dataset.json"
    cases_path = Path(__file__).with_name("eval_cases.json")
    payload = {
        "schema_version": "1",
        "artifact_kind": "evaluation-config",
        "timestamp": timestamp(),
        "model_id": model.id,
        "system_prompt": SYSTEM_PROMPT,
        "eval_cases_sha256": hashlib.sha256(cases_path.read_bytes()).hexdigest(),
        "eval_cases": cases,
        "promptfoo_config_sha256": hashlib.sha256(promptfoo_config.read_bytes()).hexdigest(),
        "promptfoo_config": promptfoo_config.read_text(),
        "promptfoo_dataset_sha256": hashlib.sha256(promptfoo_dataset.read_bytes()).hexdigest(),
    }
    destination = RESULTS / f"evaluation-config-{model.id}-{timestamp_slug()}.json"
    atomic_write_json(destination, payload)
    return destination


def run(repo: Path, model: ai.Model, port: int) -> tuple[Path, dict[str, object], Path, Path]:
    cases_path = Path(__file__).with_name("eval_cases.json")
    cases = json.loads(cases_path.read_text())
    command = ai.server_command(repo, model.id, port=port)
    runtime_dir = repo / ".runtime"
    runtime_dir.mkdir(exist_ok=True)
    log_path = runtime_dir / f"ai-eval-{model.id}.log"
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
            results: list[dict[str, object]] = []
            for case in cases:
                response, wall_time, error = _completion(port, model.id, case["request"])
                parsed = _extract_object(response)
                passed, detail = _evaluate(case, parsed) if error is None else (False, error)
                results.append(
                    {
                        "id": case["id"],
                        "category": case["category"],
                        "passed": passed,
                        "wall_time_seconds": wall_time,
                        "response": response,
                        "parsed": parsed,
                        "detail": detail,
                    }
                )
            promptfoo_path = _run_promptfoo(repo, model.id, port)
        finally:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=20)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait(timeout=5)
    passed = sum(bool(result["passed"]) for result in results)
    identity = ai.runtime_identity()
    payload: dict[str, object] = {
        "schema_version": "1",
        "benchmark": "ai-deterministic-eval",
        "timestamp": timestamp(),
        "host": host_provenance(),
        "runtime": {
            "name": "llama.cpp",
            "version": identity["llama_version"],
            "backend": identity["llama_devices"],
        },
        "model": model_provenance(model),
        "configuration": {
            "context_tokens": 2048,
            "threads": THREADS,
            "temperature": 0,
            "cases_digest": hashlib.sha256(cases_path.read_bytes()).hexdigest(),
        },
        "cases": results,
        "aggregate": {
            "passed": passed,
            "total": len(results),
            "pass_ratio": passed / len(results),
        },
        "caveats": [
            "all assertions are deterministic; no LLM judge or paid API is used",
            "generated Python executes only after AST restriction to a tiny expression subset",
            "these synthetic cases measure bounded task behavior, not general intelligence",
        ],
    }
    destination = RESULTS / f"ai-eval-{model.id}-{timestamp_slug()}.json"
    atomic_write_json(destination, payload)
    config_path = _write_evaluation_config(repo, model, cases)
    return destination, payload, promptfoo_path, config_path


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
    path, result, promptfoo_path, config_path = run(
        repo, model, int(os.environ.get("HOME_LAB_AI_EVAL_PORT", "18082"))
    )
    print(path)
    print(promptfoo_path)
    print(config_path)
    api_paths = sorted((repo / "benchmarks" / "results").glob(f"ai-api-{model.id}-*.json"))
    if api_paths:
        api_result = json.loads(api_paths[-1].read_text())
        metrics_path = publish_to_guest(repo, render_ai_metrics(api_result, result))
        print(metrics_path)
    log_evidence(repo, "eval", [path, promptfoo_path, config_path])
    aggregate_result = result["aggregate"]
    return 0 if isinstance(aggregate_result, dict) and aggregate_result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
