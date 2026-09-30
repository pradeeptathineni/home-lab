# 0001 - portable Linux node before dedicated hardware

status: accepted
date: 2026-09-30

## Context

The MacBook is the only real compute host. The service environment still needs
Linux host semantics and a migration path.

## Decision

Run Debian 13 under Lima using Virtualization.framework. Mount source read-only
and keep state under `/srv/home-lab`.

## Consequences

The lab stops with the laptop. Ansible can later converge a Debian server VM
without redesigning the application layer.
