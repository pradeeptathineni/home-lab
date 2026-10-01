# Operations

`labctl` prints the tools it invokes. Docker, Lima, Ansible, llama.cpp, and
restic remain directly usable when deeper inspection is needed.

```console
./bin/labctl doctor
./bin/labctl node up
./bin/labctl node converge
./bin/labctl secrets init
./bin/labctl deploy core
./bin/labctl deploy observability-full
./bin/labctl deploy network-lab
./bin/labctl deploy ai
./bin/labctl deploy knowledge
./bin/labctl status
./bin/labctl logs homarr
./bin/labctl stop knowledge
```

Set `LABCTL_TARGET=local` only for host-side Compose validation or a deliberate
Docker Desktop test. The operating target defaults to Lima.

## Services and credentials

The first Homarr run requires creating its real administrator through the UI.
Important dashboard links are intentionally small manual state until Homarr
offers a stable supported declarative import for them. Its app data belongs in
backup scope.

## Local AI

The registry is declarative; models and runtime binaries remain outside Git.
`fetch` prints the exact source, revision, license, size, digest, and phase budget
before downloading and refuses to replace an unexpected file.

```console
./bin/labctl ai inspect
./bin/labctl ai models
./bin/labctl ai fetch granite4-1b-q4km
./bin/labctl ai serve granite4-1b-q4km
./bin/labctl ai benchmark granite4-1b-q4km
./bin/labctl ai eval granite4-1b-q4km
./bin/labctl ai compare
./bin/labctl ai route start
./bin/labctl deploy ai
./bin/labctl ai webui configure
./bin/labctl ai route stop
./bin/labctl ai stop
```

Start the native server before the route. The route requires the primary Lima
node and writes an owned SSH-process record under ignored `.runtime/`. The WebUI
configuration command authenticates through Open WebUI's supported API using
guest-resident secrets, preserves existing connections, and verifies model
listing plus a completion without printing credentials. Stop optional AI
services after use; MLflow alone used about 2.2 GiB in the measured profile.

Run retrieval separately with `./bin/labctl ai retrieval
qwen3-embed-0.6b-q8`. It temporarily owns an embedding server and does not
ingest Paperless, Syncthing, or personal documents.

## Disposable sandbox

```console
./bin/labctl sandbox create
./bin/labctl sandbox verify
./bin/labctl sandbox experiment network-fault
./bin/labctl sandbox stop
./bin/labctl sandbox start
./bin/labctl sandbox destroy --yes
```

The fixed name is `home-lab-sandbox`. `create` refuses an existing instance,
`destroy` requires `--yes`, and all lifecycle commands refuse to target the
primary node. Verification writes the latest private network report only to the
planning output directory when that directory exists. Destroy the sandbox after
the experiment; it has no backup contract.

Generated administrator credentials live only in the guest at
`/srv/home-lab/secrets/runtime.env`. `labctl secrets init` adds newly required
keys without replacing existing values and keeps the file mode at `0600`.

Local URLs use the Caddy loopback entry point:

- `http://dashboard.lab.localhost:8080`
- `http://grafana.lab.localhost:8080`
- `http://ai.lab.localhost:8080`
- `http://mlflow.lab.localhost:8080`
- `http://paperless.lab.localhost:8080`
- `http://syncthing.lab.localhost:8080`

Use `./bin/labctl benchmark dns` for the isolated DNS proof and
`./bin/labctl benchmark network` for the owned Caddy health route.

No profile auto-starts at Mac boot. Laptop sleep interrupting services is
expected in portable mode.
