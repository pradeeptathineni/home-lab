# Operations

`labctl` prints the tools it invokes. Docker, Lima, Ansible, and restic remain
directly usable when deeper inspection is needed.

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

The first Homarr run requires creating its real administrator through the UI.
Important dashboard links are intentionally small manual state until Homarr
offers a stable supported declarative import for them. Its app data belongs in
backup scope.

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
`./bin/labctl benchmark network` for the owned Caddy health route. The AI
benchmark exits with status 3 until Ollama and an explicitly selected model are
available.

No profile auto-starts at Mac boot. Laptop sleep interrupting services is
expected in portable mode.
