# Architecture

## Current topology

The Mac owns source control and management tools. A Debian 13 Lima VM is the
Linux service boundary. The repository is mounted read-only at its host path;
mutable state lives at `/srv/home-lab`.

Docker Compose groups services by operational purpose. No profile is started
implicitly. Caddy is the only HTTP entry point. The DNS lab binds an explicit
high host port and never changes host or router DNS.

Native macOS is an intentional exception for inference. Upstream llama.cpp owns
the model process and binds only `127.0.0.1`. An SSH reverse forward presents a
Unix socket inside the primary VM; a capability-dropped bridge exposes that
socket only on the internal AI Compose network. Open WebUI never needs a
guest-wide or LAN-visible inference port.

## Boundaries

| Boundary | Responsibility |
| --- | --- |
| macOS | management, Git, optional Tailscale, native llama.cpp inference |
| Lima/Debian | reproducible Linux host semantics and Docker service runtime |
| Compose core | private HTTP routing and administrative dashboard |
| optional profiles | metrics, logs, DNS tests, AI experiments, knowledge tools |
| `/srv/home-lab` | mutable service data, backups, logs, and secrets |
| Git repository | desired state, tests, schemas, and reviewed evidence only |
| disposable Lima VM | no host mounts or primary state; bounded experiments |

The disposable `home-lab-sandbox` is separate from the primary node. Plain Lima
mode disables filesystem sharing, guest agent features, and dynamic port
forwarding; `mounts`, `portForwards`, and containerd are empty or disabled. Its
user-mode network provides DNS and internet egress and blocks the primary VM,
but it is not a hostile-code or internet-only boundary because deliberately
addressed Mac-host services can still be reached.

## Future topology

When real hardware exists, Proxmox is the current hypervisor hypothesis. The
Compose stack moves to a Debian service VM converged by the same Ansible roles.
Home Assistant belongs in a HAOS VM. A GPU-specific Ubuntu VM is justified only
by actual accelerator support. DNS does not become household-critical until a
physically independent fallback exists.

## Why Compose comes first

There is one portable node. Scheduling, multi-node reconciliation, distributed
storage, and rolling replacement provide no current operational benefit.
Compose keeps failure behavior visible and the emergency bundle small.
Kubernetes remains a gated learning or operating choice after hardware and
workload needs exist.
