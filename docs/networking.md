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

A future home network should use `home.arpa`, not `.local`, and consider trusted,
IoT, lab, guest, and management boundaries after real router hardware is known.
