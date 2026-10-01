# Networking

Current access is local to the Mac and Lima network. Caddy exposes development
routes under `*.lab.localhost` on port 8080. Services are not published through
router port forwarding.

Pi-hole is a lab target only. Clients must explicitly query its guest loopback
port 1053 or use the isolated test container. The stack does not alter macOS
resolvers, DHCP, or the home router.

The repository DNS probe sends raw UDP queries inside the isolated client so
container-exec overhead is not counted. The verified warm median was about
0.20 ms for five allowed and five block-test queries; caches were not forcibly
cleared, so it is a smoke measurement rather than a comparative benchmark.

Tailscale is the private-access hypothesis but remains host-level and manual.
The repository may detect it and document steps; it does not install, enroll,
log out, advertise routes, or change ACLs.

Native llama.cpp listens only on Mac loopback port 18080. `labctl ai route start`
uses SSH reverse Unix-socket forwarding to create
`/srv/home-lab/ai-route/llama.sock` in the primary VM. The Compose bridge reads
that socket and listens only on the internal `home-lab-ai` network. The verified
Open WebUI request listed the selected model and completed a prompt; no guest or
LAN TCP inference listener was present.

The disposable sandbox uses Lima plain mode and `user-v2` networking. A live
probe confirmed DNS and internet egress, no automatic inbound forward, no host
mount, and no primary-VM name resolution or Caddy access. `host.lima.internal`
still resolves, and a deliberately addressed Mac-host test port was reachable.
That limitation is recorded rather than treating the VM as an internet-only
security sandbox.

A future home network should use `home.arpa`, not `.local`, and consider trusted,
IoT, lab, guest, and management boundaries after real router hardware is known.
