#!/usr/bin/env python3
"""run an isolated Toxiproxy HTTP dependency degradation experiment"""

from __future__ import annotations

import hashlib
import json
import math
import os
import statistics
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

TOXIPROXY_VERSION = "2.12.0"
TOXIPROXY_URL = (
    "https://github.com/Shopify/toxiproxy/releases/download/v2.12.0/toxiproxy-server-linux-amd64"
)
TOXIPROXY_SHA256 = "556d891134a3c582dc1e1a3f7335fd55142e5965769855a00b944e13e48302fc"
REPETITIONS = 20
WORK = Path("/tmp/home-lab-fault-experiment")
API = "http://127.0.0.1:8474"
PROXY = "http://127.0.0.1:19081/health"


def _digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _download() -> Path:
    WORK.mkdir(parents=True, exist_ok=True)
    binary = WORK / "toxiproxy-server"
    if binary.exists() and _digest(binary) == TOXIPROXY_SHA256:
        return binary
    temporary = binary.with_suffix(".partial")
    temporary.unlink(missing_ok=True)
    with (
        urllib.request.urlopen(TOXIPROXY_URL, timeout=120) as response,
        temporary.open("wb") as handle,
    ):
        while chunk := response.read(1024 * 1024):
            handle.write(chunk)
    if _digest(temporary) != TOXIPROXY_SHA256:
        temporary.unlink(missing_ok=True)
        raise RuntimeError("Toxiproxy SHA-256 verification failed")
    os.chmod(temporary, 0o755)
    os.replace(temporary, binary)
    return binary


def _api(method: str, path: str, payload: dict[str, object] | None = None) -> object:
    body = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(
        API + path,
        data=body,
        headers={"Content-Type": "application/json"},
        method=method,
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        content = response.read()
    return json.loads(content) if content else {}


def _wait_api(process: subprocess.Popen[bytes]) -> str:
    for _ in range(100):
        if process.poll() is not None:
            raise RuntimeError("Toxiproxy exited before its API became ready")
        try:
            result = _api("GET", "/version")
            if isinstance(result, dict) and isinstance(result.get("version"), str):
                return result["version"]
            return str(result)
        except (OSError, urllib.error.URLError):
            time.sleep(0.1)
    raise RuntimeError("Toxiproxy API did not become ready")


def _wait_upstream(process: subprocess.Popen[bytes]) -> None:
    for _ in range(100):
        if process.poll() is not None:
            raise RuntimeError("synthetic upstream exited before becoming ready")
        try:
            with urllib.request.urlopen("http://127.0.0.1:19080/health", timeout=1) as response:
                if response.status == 200:
                    return
        except (OSError, urllib.error.URLError):
            time.sleep(0.05)
    raise RuntimeError("synthetic upstream did not become ready")


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[max(0, math.ceil(percentile * len(ordered)) - 1)]


def _measure(name: str, toxic: dict[str, object] | None) -> dict[str, object]:
    samples: list[dict[str, object]] = []
    for index in range(REPETITIONS):
        started = time.perf_counter()
        try:
            with urllib.request.urlopen(PROXY, timeout=2) as response:
                body = json.load(response)
            wall = (time.perf_counter() - started) * 1000
            success = response.status == 200 and body == {"status": "synthetic-ok"}
            samples.append(
                {"index": index, "success": success, "wall_time_ms": wall, "error": None}
            )
        except (OSError, ValueError, urllib.error.URLError) as error:
            samples.append(
                {
                    "index": index,
                    "success": False,
                    "wall_time_ms": (time.perf_counter() - started) * 1000,
                    "error": type(error).__name__,
                }
            )
    successful = [float(sample["wall_time_ms"]) for sample in samples if sample["success"]]
    successes = len(successful)
    return {
        "scenario": name,
        "toxic_configuration": toxic,
        "repetitions": REPETITIONS,
        "successes": successes,
        "failures": REPETITIONS - successes,
        "samples": samples,
        "aggregate": {
            "median_ms": statistics.median(successful) if successful else None,
            "p95_ms": _percentile(successful, 0.95),
            "failure_rate": (REPETITIONS - successes) / REPETITIONS,
        },
    }


def _add_latency(name: str, latency: int) -> dict[str, object]:
    toxic = {
        "name": name,
        "type": "latency",
        "stream": "downstream",
        "toxicity": 1.0,
        "attributes": {"latency": latency, "jitter": 0},
    }
    _api("POST", "/proxies/synthetic/toxics", toxic)
    return toxic


def _remove_toxic(name: str) -> None:
    _api("DELETE", f"/proxies/synthetic/toxics/{name}")


def main() -> int:
    binary = _download()
    upstream_code = (
        "from http.server import BaseHTTPRequestHandler,HTTPServer\n"
        "class H(BaseHTTPRequestHandler):\n"
        " def do_GET(self):\n"
        '  body=b\'{"status":"synthetic-ok"}\'\n'
        "  self.send_response(200);self.send_header('Content-Type','application/json');"
        "self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)\n"
        " def log_message(self,*args): pass\n"
        "HTTPServer(('127.0.0.1',19080),H).serve_forever()\n"
    )
    with (
        (WORK / "upstream.log").open("wb") as upstream_log,
        (WORK / "toxiproxy.log").open("wb") as toxiproxy_log,
    ):
        upstream = subprocess.Popen(
            [sys.executable, "-c", upstream_code],
            stdout=upstream_log,
            stderr=subprocess.STDOUT,
        )
        toxiproxy = subprocess.Popen(
            [str(binary), "-host", "127.0.0.1", "-port", "8474"],
            stdout=toxiproxy_log,
            stderr=subprocess.STDOUT,
        )
        try:
            _wait_upstream(upstream)
            reported_version = _wait_api(toxiproxy)
            _api(
                "POST",
                "/proxies",
                {
                    "name": "synthetic",
                    "listen": "127.0.0.1:19081",
                    "upstream": "127.0.0.1:19080",
                    "enabled": True,
                },
            )
            scenarios = [_measure("baseline", None)]
            toxic = _add_latency("latency-100", 100)
            scenarios.append(_measure("latency-100ms", toxic))
            _remove_toxic("latency-100")
            toxic = _add_latency("latency-500", 500)
            scenarios.append(_measure("latency-500ms", toxic))
            _remove_toxic("latency-500")
            _api("POST", "/proxies/synthetic", {"enabled": False})
            scenarios.append(_measure("dependency-down", {"proxy_enabled": False}))
            _api("POST", "/proxies/synthetic", {"enabled": True})
            scenarios.append(_measure("recovery", {"proxy_enabled": True, "toxics": []}))
        finally:
            for process in (toxiproxy, upstream):
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=2)
    recovery = scenarios[-1]
    result = {
        "schema_version": "1",
        "experiment": "synthetic-http-dependency-degradation",
        "timestamp": datetime.now(UTC).isoformat(),
        "sandbox_version": sys.argv[1] if len(sys.argv) > 1 else "unknown",
        "toxiproxy_version": reported_version,
        "scenarios": scenarios,
        "recovery_success": recovery["successes"] == REPETITIONS,
        "caveats": [
            "all requests target a synthetic HTTP server inside the disposable sandbox",
            "p95 uses 20 bounded local samples per scenario",
            "Toxiproxy and upstream logs remain under /tmp/home-lab-fault-experiment",
        ],
    }
    print(json.dumps(result))
    return 0 if result["recovery_success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
