# 0005 - native Mac inference and Linux service plane

status: superseded by 0006
date: 2026-09-30

## Context

Linux is the portable service environment, while accelerated inference on Mac
hardware is best served by the native runtime.

## Decision

Keep Ollama native on macOS when installed. Run Open WebUI and experiment
tracking in Debian and connect through `host.lima.internal`.

## Consequences

The AI profile depends on host-native state and reports absence honestly. It
does not pull models automatically. A future GPU server will be reassessed from
actual hardware and workload evidence.
