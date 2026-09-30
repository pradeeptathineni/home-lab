# 0003 - private remote access before public ingress

status: accepted
date: 2026-09-30

## Context

Administrative dashboards and Docker controls should not be exposed to the
internet for convenience.

## Decision

Prefer host-level Tailscale and LAN access. Open no router ports and publish no
service by default.

## Consequences

Remote use depends on a separately recoverable private network path. Enrollment
and ACL changes remain explicit manual operations.
