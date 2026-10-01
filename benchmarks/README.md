# Benchmarks

Generated results go to `benchmarks/results/` and are ignored. Commit a result
only after checking that it is real, useful, reproducible, and free of private
identifiers.

Every record includes a timestamp, benchmark and schema version, a generic host
class, operating environment, software and model provenance, repetitions, raw
samples, aggregates, and caveats where relevant.

```console
./bin/labctl benchmark dns
./bin/labctl benchmark network
./bin/labctl ai benchmark granite4-1b-q4km
./bin/labctl ai eval granite4-1b-q4km
./bin/labctl ai compare
./bin/labctl ai retrieval qwen3-embed-0.6b-q8
./bin/labctl sandbox experiment network-fault
```

The local AI commands never pull or remove a model. Fetches are separate,
registry-bounded operations that verify exact size and SHA-256. The engine
benchmark uses `llama-bench`; API and evaluation runners use the managed local
OpenAI-compatible server. Prompt-processing throughput, application-level TTFT,
wall time, and streamed generation rate remain distinct.

The retrieval corpus is synthetic and contains no personal files. The fault
experiment runs a synthetic HTTP server, client, and Toxiproxy entirely in the
disposable sandbox. DNS queries go only through the explicit test client. The
network runner makes a few HTTP requests to the owned Caddy health route and is
not a bandwidth test.

Successful AI runs attempt to log their JSON artifacts to the existing MLflow
profile and publish low-cardinality summaries through node exporter's textfile
collector. Failure to reach optional MLflow never converts a failed benchmark
into a success.
