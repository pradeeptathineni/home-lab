# Benchmarks

The benchmark subsystem records configuration and measurement boundaries before
claiming a comparison. AI engine, API, evaluation, retrieval, DNS, network, and
fault schemas live under `benchmarks/schema`. Generated raw results stay ignored
until reviewed and sanitized.

## Local AI method

The native runtime is upstream llama.cpp v0.5.0 at commit `7fe450e`, built for
x86_64 with Accelerate, without Metal or OpenMP. Both generation models used an
embedded chat template, 2048-token context, eight threads, and Q4_K_M
quantization.

Engine measurements used `llama-bench` with a 512-token prompt, 128 generated
tokens, and five repetitions. API measurements used one warm-up plus five
streamed OpenAI-compatible requests and kept TTFT, wall time, generation rate,
exact-response status, and peak sampled process RSS separate. The deterministic
evaluation used 15 versioned cases spanning instruction following, extraction,
formatting, classification, arithmetic, and safety. Any code assertion runs in
isolated Python with an AST allowlist. Promptfoo 0.123.1 independently executed
the same dataset through the local compatible API.

| Model | Size | Engine prompt tok/s | Engine gen tok/s | API TTFT | API gen tok/s | Deterministic | Promptfoo |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Granite 4.0 1B Q4_K_M | 1.02 GB | 174.98 | 23.90 | 62 ms | 28.07 | 6/15 | 5/15 |
| Qwen 3.5 2B Q4_K_M | 1.28 GB | 127.61 | 17.82 | 87 ms | 21.14 | 6/15 | 5/15 |

Granite is the current default because it was smaller and materially faster with
the same measured quality result. The 15-case suites are regression and
comparison fixtures, not a general intelligence score. An early Qwen run left
thinking enabled, exhausted its output cap, and produced invalid evidence; its
MLflow run is retained with `evidence_status=invalidated` and is excluded from
the table.

`labctl ai compare` writes a schema-validated ignored comparison using the
deterministic rule “highest eval pass count, then lowest median API TTFT, then
smallest artifact.” It records the source result filenames and every component
metric without producing an overall score.

## Retrieval method

Qwen 3 Embedding 0.6B Q8 used llama.cpp embedding mode, 2048-token context,
eight threads, 1024 dimensions, last-token pooling, and documented query and
document prefixes. Ten short synthetic documents and fifteen synthetic queries
were hashed and embedded whole; exact cosine ranked stable document IDs.

The run reached 15/15 Hit@1, 15/15 Hit@3, MRR 1.0, and 15/15 expected-fact
presence. Indexing took 2.15 seconds and median query latency was 53 ms. This is
a controlled plumbing proof, not evidence for personal-corpus retrieval quality.

## Fault method

The sandbox experiment downloads checksum-verified Toxiproxy 2.12.0 inside the
disposable VM and keeps both the HTTP server and client there. Each phase uses
20 requests: baseline, +100 ms latency, +500 ms latency, proxy disabled, and
recovery.

| Phase | Successes | Median | p95 |
| --- | ---: | ---: | ---: |
| baseline | 20/20 | 0.76 ms | 1.15 ms |
| +100 ms | 20/20 | 102.39 ms | 103.02 ms |
| +500 ms | 20/20 | 502.51 ms | 503.06 ms |
| disabled | 0/20 | n/a | n/a |
| recovery | 20/20 | 0.87 ms | 1.11 ms |

Recovery required full success after the proxy was re-enabled. A repeated-run
startup race was found, fixed with an explicit upstream-readiness gate, and two
subsequent complete runs passed.

AI throughput from `llama-bench` is not presented as end-to-end chat latency.
DNS distributions distinguish cold and warm queries. Network measurements run
only against explicitly owned endpoints. Storage write tests remain excluded
until an explicit disposable target is provided.

The earlier DNS smoke run recorded ten in-client UDP queries and a warm median
near 0.20 ms. The owned-route network smoke run recorded five HTTP requests to
Caddy with a median near 3.11 ms. These single-host samples establish method and
plumbing, not performance rankings.

See [the benchmark README](../benchmarks/README.md) for commands and provenance
fields.
