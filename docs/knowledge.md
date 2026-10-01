# Knowledge profile

The `knowledge` profile keeps file synchronization and document archiving
separate. Syncthing exposes an empty lab-owned data root; it does not mount or
scan the Mac home directory. Paperless-ngx owns its own consume, data, export,
and media directories under `/srv/home-lab/data`.

The repository contains one synthetic text fixture with a stable marker and
known SHA-256. After the profile is healthy, this command uploads the fixture
through Paperless's authenticated API and proves that the marker is searchable:

```console
limactl shell --workdir "$PWD" home-lab -- docker compose \
  --project-directory "$PWD" \
  --env-file /srv/home-lab/secrets/runtime.env \
  -f "$PWD/compose.yaml" --profile knowledge exec -T paperless \
  python /opt/home-lab/paperless-smoke.py
```

The proof is idempotent and prints provenance, checksum, task ID, document ID,
and query status without printing credentials. It does not send the fixture to
Open WebUI or any model.

Local retrieval remains deliberately separate from personal document ingest.
The approved Qwen 3 Embedding 0.6B Q8 artifact is digest-pinned and was tested
through llama.cpp over ten short synthetic documents and fifteen queries. The
exact-cosine runner recorded stable document IDs, source labels, corpus/query
hashes, 1024 dimensions, index time, per-query latency, ranks, and fact-presence
checks. It reached 15/15 Hit@1, 15/15 Hit@3, and MRR 1.0 with a 53 ms median
query latency. This small synthetic set proves plumbing and provenance, not a
general-purpose “second brain.”

Open WebUI's in-product RAG path is still disabled. Enabling it would require a
separately managed embedding service or deliberate runtime switching, followed
by another supported-API proof. Until then, upload no personal corpus to the AI
surface. The offline settings continue to block implicit model downloads.

No Syncthing peer is configured automatically. Pair a trusted device through
the local UI, choose a dedicated folder, and test that folder before placing
real files in it. Do not point Syncthing at the entire home directory.
