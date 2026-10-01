# Current state

Last verified: 2026-09-30

The only physical compute host is a MacBook Pro. It is not an always-on server.
The repository defines a Debian 13 Lima node and opt-in Compose profiles. The
runtime proof and exact checks are updated here only after they are run.

## Verified

- Initial repository history and MIT license were preserved.
- The Intel Core i9-9980HK Mac has 8 physical/16 logical CPUs, 64 GiB RAM,
  hardware virtualization, and roughly 571 GiB free space at discovery time.
- Lima 2.2.0 runs Debian 13.6 with 4 vCPU, 8 GiB RAM, and a 40 GiB disk.
- The repository mount is read-only and Lima forwards only Caddy on loopback
  port 8080.
- Docker Engine 29.8.1 and Compose 5.5.1 run inside the node.
- A second Ansible convergence completed with `changed=0`.
- Core, full observability, DNS lab, AI, and knowledge profiles reached healthy
  state together.
- The restricted socket proxy allowed inspect/start/stop/restart and rejected
  create and delete requests.
- All five Prometheus targets were up, Grafana provisioned four dashboards,
  and a real Caddy log query returned data from Loki.
- Pi-hole resolved `example.com`, blocked `doubleclick.net`, and remained
  isolated from Mac and router DNS.
- Upstream llama.cpp v0.5.0 runs natively with the Accelerate CPU backend. A
  Metal build did not run reliably on this Intel/AMD host, so no GPU result is
  claimed.
- Two digest-pinned generation models were benchmarked. Granite 4.0 1B Q4_K_M
  is the measured default: 28.07 median streamed tokens/s, 62 ms median TTFT,
  and 6/15 deterministic evaluation cases. Qwen 3.5 2B Q4_K_M reached 21.14
  tokens/s, 87 ms TTFT, and the same 6/15 score.
- Open WebUI reached the native server through an SSH reverse Unix socket and
  an internal-only bridge. A proxied completion passed without a cloud API or
  guest/LAN inference listener.
- MLflow contains the benchmark, evaluation, and retrieval runs. Prometheus
  scraped the generated AI metrics and Grafana provisioned the eight-panel AI
  dashboard.
- The Qwen 3 Embedding 0.6B Q8 synthetic retrieval proof reached 15/15 Hit@1,
  15/15 Hit@3, MRR 1.0, and 53 ms median query latency over ten short fixtures.
- A synthetic Paperless fixture was uploaded and found by its unique marker;
  Syncthing is healthy but intentionally has no paired device.
- Restic backup, repository check, scratch restore, and SHA-256 verification
  passed against a private local development repository.
- The handoff state keeps core and full observability active. Their containers
  used roughly 1.05 GiB combined, while the VM reported 1.7 GiB used and 6 GiB
  available.
- The disposable sandbox was created, stopped, restarted, verified, and
  destroyed. It had no host mount, Docker socket, primary state, or inbound
  dynamic forwarding. It could not resolve or reach the primary VM. A local
  Toxiproxy experiment proved baseline, +100 ms, +500 ms, total failure, and
  recovery behavior with 20 samples per phase.

## Conditional

- Tailscale is not installed. No device was enrolled and no login state was changed.
- Ollama remains absent and unused. The measured path is upstream llama.cpp.
- Open WebUI runs in offline mode. Its private generation route is proved, but
  its in-product RAG path is not configured; the reproducible external
  embedding benchmark is the current retrieval evidence.
- No external restic target is configured. The local development repository
  proves mechanics but does not provide resilient backup.
- Homarr still needs its first administrator and small set of dashboard links
  created through the UI.
- Syncthing needs an explicitly approved peer and folder before it can prove
  device-to-device synchronization.
- The active AI proof snapshot used about 639 MiB for Open WebUI, 2.217 GiB for
  MLflow, 6 MiB for the socket bridge, and 1.864 GiB native RSS for Granite:
  roughly 4.71 GiB across the service and inference planes. AI, knowledge, and
  DNS therefore remain start-on-demand profiles and were stopped after
  validation.
- Lima `user-v2` networking isolates the sandbox from the primary VM and host
  mounts, but an explicitly addressed Mac-host service remains reachable. The
  sandbox is disposable containment, not an internet-only security boundary.

## Not present

- dedicated server or Proxmox installation;
- dedicated GPU server;
- router-managed lab VLANs;
- network-wide DNS;
- independent secondary resolver;
- Home Assistant or physical sensors;
- Kubernetes cluster;
- public ingress or availability guarantee.

The lab disappears when the Mac sleeps. That is normal for the current phase.
