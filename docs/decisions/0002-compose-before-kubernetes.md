# 0002 - Compose before Kubernetes

status: accepted
date: 2026-09-30

## Context

There is one non-always-on node and no need for cross-node scheduling.

## Decision

Use modular Docker Compose profiles. Defer k3s and GitOps controllers.

## Consequences

Operations remain direct and portable. Multi-node reconciliation is unavailable
until it solves an actual problem and its cost is accepted.
