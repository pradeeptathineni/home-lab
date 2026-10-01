# home-lab

This is the infrastructure I use to run and measure services at home, built out
primarily from my laptop. I do not have a dedicated always-on server yet, so the
current node is a Debian VM on my MacBook. The service layer is portable now and
is meant to move to the eventual server without being rewritten.

The useful parts are repeatability, visibility, isolation, recovery, and
numbers I can compare instead of guesses.

## Current state

- The MacBook is the only physical compute host.
- Linux runs under Lima; nothing is guaranteed to be available when the laptop
  sleeps or leaves the network.
- The dedicated server, router segmentation, and secondary DNS node are plans,
  not present hardware.
- Tailscale remains an optional host-native integration. Local AI uses an
  upstream llama.cpp build and an explicit digest-pinned model registry.

See [current state](docs/current-state.md) for verified runtime status.

## What this does

| Capability | Current state |
| --- | --- |
| portable Debian node | implemented; runtime proof recorded in current state |
| dashboard and service controls | implemented as the `core` profile |
| metrics and logs | implemented as opt-in observability profiles |
| Pi-hole | isolated `network-lab` profile only |
| local AI | two generation models benchmarked; Granite 4.0 1B is the measured default |
| local retrieval | synthetic 15-query embedding proof passed; personal ingest remains gated |
| disposable sandbox | reproducible Lima lifecycle and Toxiproxy fault proof passed |
| document sync and archive | profile healthy; synthetic Paperless proof passed |
| backup and restore check | local mechanics proved; external target still required |
| always-on server | planned; no hardware acquired |
| router-wide DNS | gated on always-on hardware and independent fallback |
| Home Assistant | planned for a future HAOS VM |
| Kubernetes | deliberately deferred |

## Architecture

```mermaid
flowchart TB
  subgraph MacBook["MacBook Pro (current physical host)"]
    Git["Git / editor / labctl"]
    Llama["llama.cpp (native, loopback only)"]
    subgraph Lima["Lima VM: Debian 13"]
      Docker["Docker Compose"]
      Core["Caddy + Homarr"]
      Obs["observability (optional)"]
      DNS["DNS lab (optional)"]
      AI["AI and knowledge profiles (optional)"]
      Docker --> Core
      Docker --> Obs
      Docker --> DNS
      Docker --> AI
    end
    Git --> Lima
    AI -. SSH reverse Unix socket .-> Llama
  end
```

The full current and future topology is in [architecture](docs/architecture.md).

## Run it

```console
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
./bin/labctl doctor
./bin/labctl node up
./bin/labctl node converge
./bin/labctl secrets init
./bin/labctl deploy core
./bin/labctl status
./bin/labctl validate
```

Copy `config/example.env` to a private file outside Git and set the required
secrets before starting stateful profiles. `labctl doctor` explains missing
values without printing their contents.

## Profiles

- `core`: Caddy, Homarr, and a restricted Docker socket proxy
- `observability`: Prometheus, Grafana, node/container metrics, and probes
- `observability-full`: Loki and Alloy in addition to observability
- `network-lab`: Pi-hole on an explicit test port; no system DNS changes
- `ai`: offline Open WebUI, a private bridge to native llama.cpp, and MLflow
- `knowledge`: Syncthing and Paperless-ngx with empty, explicit data roots

## Evidence

Benchmark, evaluation, retrieval, and fault-injection methods and schemas live
in [benchmarks](benchmarks/README.md).
Generated results are ignored until they have been reviewed and sanitized.
Important dashboards are provisioned from the repository rather than existing
only in an application database.

The privacy boundary and synthetic Paperless proof are documented in
[knowledge](docs/knowledge.md).

The model files stay outside Git under the user application-support directory.
List and verify them with `./bin/labctl ai models`; no command replaces a
mismatched artifact. The disposable VM is likewise explicit: create it with
`./bin/labctl sandbox create`, verify its measured boundaries, and destroy it
with `./bin/labctl sandbox destroy --yes`.

## Server path

The eventual dedicated server is expected to run Proxmox with a Debian service
VM. The same Ansible roles and Compose application should move there. Actual
inventory will be added only after hardware exists. See the [roadmap](docs/roadmap.md).

## Repository map

| Path | Purpose |
| --- | --- |
| `labctl/`, `bin/labctl` | small human-scale operations wrapper |
| `infra/lima` | portable and disposable Linux VM definitions |
| `infra/ansible` | reusable Debian host convergence |
| `services` | profile-specific Compose and provisioned configuration |
| `benchmarks` | schemas, runners, and reviewed evidence |
| `docs` | operating model, security, recovery, and decisions |
| `config` | safe examples; no runtime secrets or state |
