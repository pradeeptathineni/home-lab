from __future__ import annotations

from pathlib import Path

from labctl.metrics import atomic_write, render_ai_metrics


def _api_result() -> dict[str, object]:
    return {
        "timestamp": "2026-09-30T12:00:00+00:00",
        "model": {"id": "tiny", "quantization": "Q4_K_M", "bytes": 123},
        "aggregate": {
            "generation_tokens_per_second": {"median": 4.5},
            "ttft_seconds": {"median": 0.25},
            "wall_time_seconds": {"median": 1.5},
        },
        "memory": {"process_rss_bytes_peak": None},
    }


def test_prometheus_output_uses_only_bounded_labels() -> None:
    output = render_ai_metrics(
        _api_result(),
        {
            "model": {"id": "tiny", "quantization": "Q4_K_M"},
            "aggregate": {"pass_ratio": 0.75},
        },
    )
    assert 'model="tiny",runtime="llama.cpp",quantization="Q4_K_M"' in output
    assert "home_lab_ai_eval_pass_ratio" in output
    assert "process_rss" not in output
    assert 'timestamp="' not in output
    assert "run_id=" not in output


def test_missing_metrics_are_omitted() -> None:
    result = _api_result()
    result["aggregate"] = {
        "generation_tokens_per_second": None,
        "ttft_seconds": None,
        "wall_time_seconds": None,
    }
    output = render_ai_metrics(result)
    assert "home_lab_ai_generation_tokens_per_second" not in output
    assert "home_lab_ai_model_bytes" in output


def test_atomic_metric_write_replaces_complete_file(tmp_path: Path) -> None:
    destination = tmp_path / "home_lab_ai.prom"
    atomic_write(destination, "first\n")
    atomic_write(destination, "second\n")
    assert destination.read_text() == "second\n"
    assert list(tmp_path.iterdir()) == [destination]
