#!/usr/bin/env python3
"""measure synthetic known-answer retrieval with a local embedding model"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
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
    host_provenance,
    model_provenance,
    timestamp,
    timestamp_slug,
)
from benchmarks.ai.run import THREADS, _wait_for_server
from labctl import ai
from labctl.mlflow import log_evidence

DOCUMENT_PREFIX = "Represent this document for retrieval: "
QUERY_PREFIX = "Represent this query for retrieving relevant documents: "
CONTEXT = 2048


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_fixtures(root: Path) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    documents = json.loads((root / "documents.json").read_text())
    queries = json.loads((root / "queries.json").read_text())
    if not isinstance(documents, list) or not 10 <= len(documents) <= 20:
        raise ValueError("retrieval corpus must contain 10-20 documents")
    if not isinstance(queries, list) or not 10 <= len(queries) <= 20:
        raise ValueError("retrieval query set must contain 10-20 queries")
    document_ids = {document["id"] for document in documents}
    if len(document_ids) != len(documents):
        raise ValueError("retrieval document IDs must be unique")
    for query in queries:
        expected = query["relevant_document_id"]
        if expected not in document_ids:
            raise ValueError(f"query {query['id']} references missing document {expected}")
        source = next(document for document in documents if document["id"] == expected)
        if query["expected_fact"].casefold() not in source["text"].casefold():
            raise ValueError(f"query {query['id']} expected fact is absent from its source")
    return documents, queries


def _server_command(repo: Path, model: ai.Model, port: int) -> list[str]:
    if model.role != "embedding":
        raise ValueError(f"model {model.id} is not an embedding model")
    state, _ = ai._installed_state(model)
    if state != "installed":
        raise RuntimeError(f"model {model.id} is {state}")
    server = ai.find_binary("llama-server")
    if not server:
        raise RuntimeError("llama-server is not installed")
    return [
        server,
        "--model",
        str(ai.model_path(model)),
        "--alias",
        model.id,
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
        "--ctx-size",
        str(CONTEXT),
        "--threads",
        str(THREADS),
        "--embedding",
        "--pooling",
        "last",
        "--metrics",
        "--no-webui",
    ]


def _embed(port: int, model_id: str, texts: list[str]) -> list[list[float]]:
    body = json.dumps({"model": model_id, "input": texts}).encode()
    request = urllib.request.Request(
        f"http://127.0.0.1:{port}/v1/embeddings",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=240) as response:
            result = json.load(response)
    except (OSError, urllib.error.URLError, json.JSONDecodeError) as error:
        raise RuntimeError(f"embedding request failed: {error}") from error
    data = result.get("data")
    if not isinstance(data, list) or len(data) != len(texts):
        raise RuntimeError("embedding response did not match the request count")
    vectors = [item.get("embedding") for item in data]
    if not all(isinstance(vector, list) and vector for vector in vectors):
        raise RuntimeError("embedding response contained an invalid vector")
    dimensions = {len(vector) for vector in vectors}
    if len(dimensions) != 1:
        raise RuntimeError("embedding response dimensions were inconsistent")
    return [[float(value) for value in vector] for vector in vectors]


def _cosine(left: list[float], right: list[float]) -> float:
    numerator = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if not left_norm or not right_norm:
        return 0.0
    return numerator / (left_norm * right_norm)


def run(repo: Path, model: ai.Model, port: int) -> tuple[Path, dict[str, object]]:
    fixture_root = Path(__file__).resolve().parent
    documents_path = fixture_root / "documents.json"
    queries_path = fixture_root / "queries.json"
    documents, queries = _load_fixtures(fixture_root)
    runtime_dir = repo / ".runtime"
    runtime_dir.mkdir(exist_ok=True)
    log_path = runtime_dir / f"ai-retrieval-{model.id}.log"
    command = _server_command(repo, model, port)
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
            index_started = time.perf_counter()
            document_vectors = _embed(
                port, model.id, [DOCUMENT_PREFIX + document["text"] for document in documents]
            )
            index_seconds = time.perf_counter() - index_started
            results: list[dict[str, object]] = []
            for query in queries:
                started = time.perf_counter()
                query_vector = _embed(port, model.id, [QUERY_PREFIX + query["query"]])[0]
                scores = [
                    (document["id"], _cosine(query_vector, vector))
                    for document, vector in zip(documents, document_vectors, strict=True)
                ]
                ranking = sorted(scores, key=lambda item: (-item[1], item[0]))
                latency = time.perf_counter() - started
                expected = query["relevant_document_id"]
                rank = next(index + 1 for index, item in enumerate(ranking) if item[0] == expected)
                top_ids = [item[0] for item in ranking[:3]]
                expected_document = next(item for item in documents if item["id"] == expected)
                results.append(
                    {
                        "id": query["id"],
                        "query": query["query"],
                        "relevant_document_id": expected,
                        "expected_fact": query["expected_fact"],
                        "expected_fact_present": query["expected_fact"].casefold()
                        in expected_document["text"].casefold(),
                        "rank": rank,
                        "top_document_ids": top_ids,
                        "top_scores": [item[1] for item in ranking[:3]],
                        "latency_seconds": latency,
                    }
                )
        finally:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=20)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait(timeout=5)
    latencies = [float(result["latency_seconds"]) for result in results]
    hit_at_1_count = sum(int(result["rank"] == 1) for result in results)
    hit_at_3_count = sum(int(result["rank"] <= 3) for result in results)
    identity = ai.runtime_identity()
    payload: dict[str, object] = {
        "schema_version": "1",
        "benchmark": "ai-retrieval",
        "timestamp": timestamp(),
        "host": host_provenance(),
        "runtime": {
            "name": "llama.cpp",
            "version": identity["llama_version"],
            "backend": identity["llama_devices"],
        },
        "model": model_provenance(model),
        "configuration": {
            "dimensions": len(document_vectors[0]),
            "context_tokens": CONTEXT,
            "threads": THREADS,
            "pooling": "last",
            "chunk_size": "whole synthetic document; maximum 125 characters",
            "overlap": 0,
            "document_prefix": DOCUMENT_PREFIX,
            "query_prefix": QUERY_PREFIX,
            "corpus_sha256": _digest(documents_path),
            "query_set_sha256": _digest(queries_path),
            "documents": len(documents),
            "queries": len(queries),
            "index_time_seconds": index_seconds,
        },
        "queries": results,
        "aggregate": {
            "hit_at_1_count": hit_at_1_count,
            "hit_at_1": hit_at_1_count / len(results),
            "hit_at_3_count": hit_at_3_count,
            "hit_at_3": hit_at_3_count / len(results),
            "mrr": sum(1 / int(result["rank"]) for result in results) / len(results),
            "expected_fact_presence_count": sum(
                int(result["expected_fact_present"]) for result in results
            ),
            "latency_seconds": aggregate(latencies),
        },
        "server_log": str(log_path),
        "caveats": [
            "the corpus is synthetic and intentionally small",
            "whole-document chunks avoid confounding chunk-boundary effects",
            "retrieval quality is measured separately from answer generation quality",
            "the index is an in-memory exact cosine scan, not a vector database",
        ],
    }
    destination = RESULTS / f"ai-retrieval-{model.id}-{timestamp_slug()}.json"
    atomic_write_json(destination, payload)
    return destination, payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo = Path(__file__).resolve().parents[2]
    model = ai.load_registry(repo).get(args.model)
    if model.role != "embedding":
        print(f"{model.id} is not an embedding model", file=sys.stderr)
        return 2
    path, result = run(repo, model, int(os.environ.get("HOME_LAB_AI_RETRIEVAL_PORT", "18083")))
    print(path)
    log_evidence(repo, "retrieval", [path])
    aggregate_result = result["aggregate"]
    return 0 if isinstance(aggregate_result, dict) and aggregate_result["hit_at_3"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
