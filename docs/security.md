# Security

- No service is public by default.
- Real secrets and mutable state stay outside Git.
- The repository does not change router DNS, host DNS, or Tailscale enrollment.
- Containers receive dropped capabilities, read-only filesystems, non-root users,
  or `no-new-privileges` where the application supports them.
- Each exception is visible next to the service configuration.

Docker control is root-equivalent. Homarr talks to a dedicated socket proxy.
The proxy enables inspection plus container start, stop, and restart. Generic
POST access, removal, creation, exec, images, volumes, networks, secrets, and
system operations remain disabled.

The dashboard is an administrative surface. Keep it on the local/private
network and use application authentication.

The known service exceptions are narrow and explicit:

- cAdvisor is privileged for cgroup, device, and Docker metric visibility;
- Homarr keeps its image-default root startup because its bundled nginx changes
  identity and prepares an internal runtime tree;
- Pi-hole and Paperless keep their image-managed capability model but still use
  `no-new-privileges`;
- Syncthing owns only its dedicated state root and no Mac home-directory mount;
- Open WebUI is offline by default so startup cannot fetch embedding, reranking,
  or speech models.
- llama.cpp accepts traffic only on Mac loopback; the primary VM receives a
  mode-`0660` Unix socket, and its bridge is internal-network-only, read-only,
  non-root, capability-dropped, and `no-new-privileges`.
- GGUF model artifacts are treated as data: the registry admits exact files and
  digests, and no remote model code or `trust_remote_code` path is enabled.

All host-facing bindings are loopback-only. The Lima template has an explicit
catch-all rule that rejects automatic forwarding for guest listeners other
than Caddy.

The disposable sandbox VM has no host-directory mount, Docker socket, primary
state, dynamic inbound forwarding, or direct primary-VM route. Lima user-mode
networking can still reach explicitly addressed Mac-host services, so this is a
disposable experiment boundary rather than an internet-only security boundary.
A container is not a substitute for a VM boundary for hostile kernel work, and
this VM is not a substitute for a separate physical security lab.
