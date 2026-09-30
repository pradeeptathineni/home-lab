# Current state

Last verified: 2026-09-30

The only physical compute host is a MacBook Pro. It is not an always-on server.
The repository defines a Debian 13 Lima node and opt-in Compose profiles. The
runtime proof and exact checks are updated here only after they are run.

## Verified

- Initial repository history and MIT license were preserved.
- The Intel Mac has 16 logical CPUs, 64 GiB RAM, hardware virtualization, and
  roughly 600 GiB free space at discovery time.
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
- Open WebUI and MLflow are healthy. A real MLflow smoke run was logged.
- A synthetic Paperless fixture was uploaded and found by its unique marker;
  Syncthing is healthy but intentionally has no paired device.
- Restic backup, repository check, scratch restore, and SHA-256 verification
  passed against a private local development repository.
- The handoff state keeps core and full observability active. Their containers
  used roughly 1.05 GiB combined, while the VM reported 1.7 GiB used and 6 GiB
  available.

## Conditional

- Tailscale is not installed. No device was enrolled and no login state was changed.
- Ollama is not installed and no approved local model is present. AI inference,
  chat, promptfoo, and generation benchmarks report as not tested rather than
  producing synthetic success.
- Open WebUI runs in offline mode and cannot use knowledge retrieval until an
  approved embedding model or service is configured.
- No external restic target is configured. The local development repository
  proves mechanics but does not provide resilient backup.
- Homarr still needs its first administrator and small set of dashboard links
  created through the UI.
- Syncthing needs an explicitly approved peer and folder before it can prove
  device-to-device synchronization.
- Running every optional profile together raised VM use to about 5.2 GiB;
  MLflow alone accounted for roughly 2.15 GiB. AI, knowledge, and DNS therefore
  remain start-on-demand profiles and were stopped after validation.

## Not present

- dedicated server or Proxmox installation;
- GPU server;
- router-managed lab VLANs;
- network-wide DNS;
- independent secondary resolver;
- Home Assistant or physical sensors;
- Kubernetes cluster;
- public ingress or availability guarantee.

The lab disappears when the Mac sleeps. That is normal for the current phase.
