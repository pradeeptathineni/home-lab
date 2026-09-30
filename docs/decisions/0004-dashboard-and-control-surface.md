# 0004 - Homarr as dashboard and control surface

status: accepted
date: 2026-09-30

## Context

The lab needs a useful dashboard with bounded container lifecycle controls,
without adding a second stack manager.

## Decision

Use Homarr behind Caddy. Route Docker requests through a proxy limited to
inspection and start, stop, and restart operations.

## Consequences

Homarr is an administrative surface and requires authentication and backup.
Portainer and Dockge are deferred until a demonstrated gap exists.
