# home-lab

This project turns my personal MacBook into a small, private home lab. It runs a
repeatable Linux environment for useful services and safe experiments while I
learn what is worth moving to a future always-on server.

It favors measured results over assumptions: services are optional, important
behavior is tested, and unfinished capabilities are described honestly.

## What it can do today

| Area | Capability |
| --- | --- |
| Home dashboard | Gives me one local place to see and control the lab's services. |
| Monitoring | Tracks service health, computer and container usage, logs, and local AI measurements in dashboards. |
| Local AI | Runs a small private chat model on the laptop without a cloud AI API. Two models were measured; Granite 4.0 1B is the current laptop-sized default. |
| Local search experiments | Finds known facts in a small synthetic document set. Personal files are deliberately not ingested yet. |
| Document tools | Runs a private document archive and a folder-sync service. Synthetic upload and search are proved; real device pairing remains a manual choice. |
| DNS experiments | Runs Pi-hole as an isolated test service without changing the Mac, router, or household DNS. |
| Backup practice | Creates, checks, restores, and verifies test backups. A genuinely separate backup destination is still needed. |
| Disposable experiments | Creates a separate throwaway Linux machine, verifies its boundaries, simulates a service becoming slow or unavailable, proves recovery, and destroys the machine afterward. |

All services are private by default. Secrets, model files, personal data, and
generated measurements stay outside Git. The AI server listens only on the
laptop itself, and the project does not open router ports or use a cloud model.

## What it is not yet

- It is not always available: the lab stops when the laptop sleeps or leaves.
- It is not household-wide infrastructure: router DNS, network segmentation,
  Home Assistant, sensors, and an independent secondary resolver remain future
  work.
- It is not a resilient backup system until an external destination is chosen
  and tested.
- It is not remotely accessible through Tailscale yet.
- Its disposable experiment machine protects the main lab from ordinary tests,
  but it is not a safe place for hostile code and can still reach deliberately
  addressed services on the Mac.
- Kubernetes is intentionally deferred; one portable machine does not need it.

See [current state](docs/current-state.md) for the latest verified facts and the
[roadmap](docs/roadmap.md) for the deliberately gated next steps.

## How it fits together

The MacBook is the only physical computer. A Debian Linux virtual machine runs
the service stack. Local AI runs directly on the Mac for better performance and
is connected privately to the web interface inside Linux. A second Linux
virtual machine is created only for disposable experiments.

The same service definitions and setup automation are intended to move to a
future dedicated server without redesigning the lab.

## Start the base lab

```console
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
./bin/labctl doctor
./bin/labctl node up
./bin/labctl node converge
./bin/labctl secrets init
./bin/labctl deploy core
./bin/labctl deploy observability-full
./bin/labctl status
./bin/labctl validate
```

Copy `config/example.env` to a private file outside Git and set the required
values before starting services that need credentials. `labctl doctor` reports
what is missing without printing secret values.

The optional groups are:

- `network-lab` for isolated Pi-hole testing;
- `ai` for the private chat interface and experiment tracking;
- `knowledge` for document archiving and folder synchronization.

Exact AI, sandbox, backup, and service procedures are in the
[operations guide](docs/operations.md).

## Proof and safety

This repository keeps the setup, tests, measurement methods, dashboards, and
decisions needed to reproduce its claims. Generated measurements remain local
until reviewed.

- [Benchmarks and measured results](docs/benchmarks.md)
- [Architecture and privacy boundaries](docs/architecture.md)
- [Security model](docs/security.md)
- [Document and retrieval boundaries](docs/knowledge.md)
- [Backup and recovery](docs/recovery.md)
- [Service catalog](docs/service-catalog.md)

## Repository map

| Path | Purpose |
| --- | --- |
| `labctl/`, `bin/labctl` | simple commands for operating the lab |
| `infra/` | Linux machines and repeatable host setup |
| `services/` | optional service groups and dashboards |
| `benchmarks/` | reproducible measurements, schemas, and test fixtures |
| `docs/` | operating details, boundaries, recovery, and decisions |
| `config/` | safe examples and the verified local-model registry |
