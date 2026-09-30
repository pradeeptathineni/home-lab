# Benchmarks

Generated results go to `benchmarks/results/` and are ignored. Commit a result
only after checking that it is real, useful, reproducible, and free of private
identifiers.

Every record includes a timestamp, benchmark and schema version, a generic host
class, operating environment, software configuration, repetition count, raw
samples, aggregates, and caveats.

```console
./bin/labctl benchmark dns
./bin/labctl benchmark network
OLLAMA_MODEL=an-installed-model ./bin/labctl benchmark ai
```

The AI runner never pulls or removes a model. It exits with a clear untested
status when Ollama or an approved model is absent. DNS queries go only through
the explicit test client. The network runner makes a few HTTP requests and is
not a bandwidth test.

`llama-bench` output may be added as a separate result type when a compatible
runtime and model exist. Its raw prompt-processing and generation throughput is
not interchangeable with application-level chat latency.
