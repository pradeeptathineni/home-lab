from __future__ import annotations

import ast
import json
from pathlib import Path

from benchmarks.ai.common import aggregate
from benchmarks.ai.compare import build_comparison
from benchmarks.ai.eval import ALLOWED_AST, _evaluate, _extract_object, _write_evaluation_config
from benchmarks.ai.run import _extract_engine_samples, _metric_values, write_runtime_artifact


def test_aggregate_preserves_raw_min_median_max() -> None:
    result = aggregate([4.0, 1.0, 3.0, 2.0, 5.0])
    assert result == {
        "raw": [4.0, 1.0, 3.0, 2.0, 5.0],
        "min": 1.0,
        "median": 3.0,
        "max": 5.0,
    }


def test_engine_samples_are_kept_separate() -> None:
    raw = [
        {"n_prompt": 512, "n_gen": 0, "samples_ts": [1, 2, 3, 4, 5]},
        {"n_prompt": 0, "n_gen": 128, "samples_ts": [6, 7, 8, 9, 10]},
    ]
    prompt, generation, _ = _extract_engine_samples(raw)
    assert prompt == [1, 2, 3, 4, 5]
    assert generation == [6, 7, 8, 9, 10]


def test_warmup_is_excluded_from_api_metrics() -> None:
    samples = [
        {"warmup": True, "success": True, "ttft_seconds": 99.0},
        {"warmup": False, "success": True, "ttft_seconds": 1.0},
        {"warmup": False, "success": False, "ttft_seconds": 2.0},
    ]
    assert _metric_values(samples, "ttft_seconds") == [1.0]


def test_eval_extracts_last_json_object() -> None:
    assert _extract_object('thinking {"wrong":1} final {"answer":"blue"}') == {"answer": "blue"}


def test_eval_exact_assertion_is_deterministic() -> None:
    case = {"expected": {"answer": 42}}
    assert _evaluate(case, {"answer": 42}) == (True, "exact structured match")
    assert not _evaluate(case, {"answer": "42"})[0]


def test_eval_code_executes_only_tiny_ast_subset() -> None:
    valid = ast.parse("def add_one(value):\n    return value + 1\n")
    assert all(type(node) in ALLOWED_AST for node in ast.walk(valid))
    invalid = ast.parse("import os\ndef add_one(value):\n    return value + 1\n")
    assert any(type(node) not in ALLOWED_AST for node in ast.walk(invalid))


def test_eval_and_promptfoo_have_fifteen_cases() -> None:
    root = Path(__file__).resolve().parents[2]
    cases = json.loads((root / "benchmarks" / "ai" / "eval_cases.json").read_text())
    promptfoo = json.loads((root / "services" / "ai" / "promptfoo" / "dataset.json").read_text())
    assert len(cases) == len(promptfoo) == 15
    assert len({case["category"] for case in cases}) == 15


def test_promptfoo_disables_optional_model_thinking() -> None:
    root = Path(__file__).resolve().parents[2]
    config = (root / "services" / "ai" / "promptfoo" / "promptfooconfig.yaml").read_text()
    assert "{{ env.AI_MODEL_ID }}" in config
    assert "{{ env.LLAMA_BASE_URL }}" in config
    assert "showThinking: false" in config
    assert "enable_thinking: false" in config


def test_promptfoo_structured_assertions_parse_provider_text() -> None:
    root = Path(__file__).resolve().parents[2]
    dataset = json.loads((root / "services" / "ai" / "promptfoo" / "dataset.json").read_text())
    javascript = [
        assertion["value"]
        for case in dataset
        for assertion in case["assert"]
        if assertion["type"] == "javascript"
    ]
    assert javascript
    assert all("JSON.parse(output)" in assertion for assertion in javascript)


def test_comparison_uses_measured_tie_breaker(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2]
    for model_id, ttft, model_bytes in (
        ("qwen35-2b-q4km", 0.09, 1_280_835_840),
        ("granite4-1b-q4km", 0.06, 1_023_645_440),
    ):
        model = {"id": model_id, "bytes": model_bytes}
        (tmp_path / f"ai-engine-{model_id}-1.json").write_text(
            json.dumps(
                {
                    "model": model,
                    "aggregate": {
                        "prompt_tokens_per_second": {"median": 100},
                        "generation_tokens_per_second": {"median": 20},
                    },
                }
            )
        )
        (tmp_path / f"ai-api-{model_id}-1.json").write_text(
            json.dumps(
                {
                    "model": model,
                    "aggregate": {
                        "ttft_seconds": {"median": ttft},
                        "generation_tokens_per_second": {"median": 20},
                        "wall_time_seconds": {"median": 0.3},
                        "failures": 0,
                    },
                    "memory": {"process_rss_bytes_peak": model_bytes * 2},
                }
            )
        )
        (tmp_path / f"ai-eval-{model_id}-1.json").write_text(
            json.dumps({"model": model, "aggregate": {"passed": 6, "total": 15}})
        )
    comparison = build_comparison(root, tmp_path)
    assert comparison["measured_default"] == "granite4-1b-q4km"


def test_mlflow_support_artifacts_capture_runtime_and_eval_config(
    tmp_path: Path, monkeypatch
) -> None:
    root = Path(__file__).resolve().parents[2]
    model = (
        __import__("labctl.ai", fromlist=["load_registry"])
        .load_registry(root)
        .get("granite4-1b-q4km")
    )
    monkeypatch.setattr("benchmarks.ai.run.RESULTS", tmp_path)
    monkeypatch.setattr("benchmarks.ai.eval.RESULTS", tmp_path)
    runtime_path = write_runtime_artifact(
        model,
        {"name": "llama.cpp", "version": "test", "backend": "Accelerate"},
        {
            "host": {"class": "test"},
            "runtime_metadata": {"commit": "test"},
            "configuration": {"threads": 8},
        },
        {"configuration": {"context_tokens": 2048}, "power": {"source": "unknown"}},
    )
    cases = json.loads((root / "benchmarks" / "ai" / "eval_cases.json").read_text())
    config_path = _write_evaluation_config(root, model, cases)
    assert json.loads(runtime_path.read_text())["artifact_kind"] == "runtime-metadata"
    config = json.loads(config_path.read_text())
    assert config["artifact_kind"] == "evaluation-config"
    assert len(config["eval_cases"]) == 15
