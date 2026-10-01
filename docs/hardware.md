# Hardware

## Current

The MacBook Pro is the only physical compute host. The verified inventory is an
Intel Core i9-9980HK with 8 physical/16 logical cores, 64 GiB memory, Intel UHD
630 plus AMD Radeon Pro 5500M graphics, and roughly 571 GiB free space. Exact
serial numbers, device identifiers, interface addresses, and hostnames are
intentionally omitted.

The default VM allocation is 4 vCPU, 8 GiB memory, and a 40 GiB disk. It is a
starting point derived from the current host, not a benchmark conclusion.

The stable llama.cpp v0.5.0 Metal build hung during the bounded runtime probe on
this Intel/AMD configuration. The accepted evidence therefore uses the native
Accelerate CPU backend with eight inference threads. GPU acceleration remains
unproved; device inventory is not performance evidence.

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
