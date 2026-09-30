# Benchmarks

The benchmark subsystem records configuration and measurement boundaries before
claiming a comparison. AI generation, DNS, and network schemas live under
`benchmarks/schema`. Generated raw results are ignored by default.

AI throughput from `llama-bench` is not presented as end-to-end chat latency.
DNS distributions distinguish cold and warm queries. Network measurements run
only against explicitly owned endpoints. Storage write tests are excluded
until an explicit disposable target is provided.

The 2026-09-30 DNS smoke run recorded ten in-client UDP queries and a warm
median near 0.20 ms. The owned-route network smoke run recorded five HTTP
requests to Caddy with a median near 3.11 ms. Generated JSON stays ignored and
local until reviewed. These single-host samples establish method and plumbing,
not performance rankings.

See [the benchmark README](../benchmarks/README.md) for commands and provenance fields.
