# Hardware

## Current

The MacBook Pro is the only physical compute host. It has enough CPU, memory,
disk, and hardware-virtualization support for a bounded portable node. Exact
serial numbers, device identifiers, interface addresses, and hostnames are
intentionally omitted.

The default VM allocation is 4 vCPU, 8 GiB memory, and a 40 GiB disk. It is a
starting point derived from the current host, not a benchmark conclusion.

## Dedicated server

No dedicated server has been acquired. Selection criteria are:

- reliable virtualization support;
- memory headroom for isolated service and experiment VMs;
- storage with a testable replacement and backup path;
- multiple useful network interfaces only if segmentation requires them;
- idle power and noise appropriate for a home;
- optional accelerator only when a measured workload justifies it.

Actual CPU, RAM, storage, NIC, power, and accelerator inventory will be added
after hardware is physically installed.
