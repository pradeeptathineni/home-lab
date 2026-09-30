#!/usr/bin/env python3
"""create private runtime values without printing them"""

from __future__ import annotations

import argparse
import os
import secrets
import sys
from pathlib import Path

DEFAULT_DESTINATION = Path("/srv/home-lab/secrets/runtime.env")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--destination", type=Path, default=DEFAULT_DESTINATION)
    return parser


def _values() -> dict[str, str]:
    return {
        "TZ": os.environ.get("TZ", "America/New_York"),
        "LAB_DATA_ROOT": "/srv/home-lab",
        "LAB_BACKUP_ROOT": "/srv/home-lab/backups",
        "LAB_UID": "1000",
        "LAB_GID": "1000",
        "HOMARR_SECRET_ENCRYPTION_KEY": secrets.token_hex(32),
        "GRAFANA_ADMIN_USER": "admin",
        "GRAFANA_ADMIN_PASSWORD": secrets.token_urlsafe(24),
        "PIHOLE_PASSWORD": secrets.token_urlsafe(24),
        "PAPERLESS_SECRET_KEY": secrets.token_urlsafe(48),
        "PAPERLESS_ADMIN_USER": "admin",
        "PAPERLESS_ADMIN_PASSWORD": secrets.token_urlsafe(24),
        "OLLAMA_BASE_URL": "http://host.lima.internal:11434",
        "OPEN_WEBUI_ADMIN_EMAIL": "admin@home.lab",
        "OPEN_WEBUI_ADMIN_PASSWORD": secrets.token_urlsafe(24),
        "WEBUI_SECRET_KEY": secrets.token_hex(32),
    }


def create(destination: Path) -> bool:
    if destination.exists():
        return False
    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    values = _values()
    payload = "".join(f"{key}={value}\n" for key, value in values.items())
    destination.write_text(payload)
    destination.chmod(0o600)
    return True


def ensure(destination: Path) -> str:
    if create(destination):
        return "created"

    payload = destination.read_text()
    present = {
        line.split("=", 1)[0]
        for line in payload.splitlines()
        if line and not line.startswith("#") and "=" in line
    }
    # preserve operator values and append only newly required keys
    missing = {key: value for key, value in _values().items() if key not in present}
    if not missing:
        destination.chmod(0o600)
        return "already complete"
    separator = "" if payload.endswith("\n") else "\n"
    addition = "".join(f"{key}={value}\n" for key, value in missing.items())
    destination.write_text(f"{payload}{separator}{addition}")
    destination.chmod(0o600)
    return "updated"


def main(argv: list[str] | None = None) -> int:
    destination = build_parser().parse_args(argv).destination
    state = ensure(destination)
    print(f"runtime env {state}: {destination}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
