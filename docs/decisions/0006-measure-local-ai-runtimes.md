# 0006 - measure local AI runtimes and isolate experiments

status: accepted
date: 2026-09-30
supersedes: 0005

## Context

The lab needed a real local inference path, comparative model evidence,
retrieval provenance, and a repeatable environment for disruptive experiments.
The Intel Mac, portable Lima node, privacy boundary, and seven-GiB download cap
constrain the solution. Ollama is absent, and a stable llama.cpp Metal build did
not run reliably on the Intel/AMD hardware.

## Decision

Build upstream llama.cpp v0.5.0 natively with the Accelerate CPU backend. Keep
models in an explicit revision-, size-, license-, and SHA-256-pinned registry.
Select Granite 4.0 1B Q4_K_M as the current default because it is smaller and
faster than the measured Qwen 3.5 2B alternative with the same deterministic
evaluation score.

Bind inference to Mac loopback and connect Open WebUI through an SSH reverse
Unix socket plus an internal-only Compose bridge. Record raw engine throughput,
application latency, deterministic evaluation, synthetic retrieval, MLflow
runs, Prometheus metrics, and a provisioned Grafana dashboard as distinct
evidence classes.

Use a separate fixed-name Lima VM for experiments. Plain mode, no mounts, no
containerd, no explicit forwards, and user-mode networking keep it detached
from primary state. Every fault experiment is synthetic and self-contained,
and the lifecycle ends in explicit destruction.

## Consequences

Generation and retrieval are local and reproducible without a cloud API, but
current inference is CPU-only. Open WebUI generation is proved; its RAG path
remains gated. The small deterministic suites establish comparative plumbing,
not broad model quality.

The sandbox can use DNS and internet egress and cannot reach the primary VM in
the measured configuration. It can still reach deliberately addressed Mac-host
services through Lima user networking, so it must not be described as an
internet-only or hostile-code boundary.
