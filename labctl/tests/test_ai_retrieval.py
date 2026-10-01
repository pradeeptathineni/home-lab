from __future__ import annotations

from pathlib import Path

import pytest

from benchmarks.retrieval.run import _cosine, _load_fixtures


def test_cosine_orders_identical_vector_first() -> None:
    assert _cosine([1.0, 0.0], [1.0, 0.0]) == pytest.approx(1.0)
    assert _cosine([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)


def test_retrieval_fixtures_are_synthetic_and_grounded() -> None:
    root = Path(__file__).resolve().parents[2] / "benchmarks" / "retrieval"
    documents, queries = _load_fixtures(root)
    assert len(documents) == 10
    assert len(queries) == 15
    assert all(document["provenance"] == "synthetic-fixture-v1" for document in documents)
    assert all("synthetic" in document["text"].lower() for document in documents)
