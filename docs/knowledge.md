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

Open WebUI knowledge remains deliberately separate. A user may upload a chosen
public or synthetic file after an approved local embedding model exists. The
default offline configuration blocks automatic model downloads, so retrieval
is expected to remain unavailable until that explicit choice is made.

No Syncthing peer is configured automatically. Pair a trusted device through
the local UI, choose a dedicated folder, and test that folder before placing
real files in it. Do not point Syncthing at the entire home directory.
