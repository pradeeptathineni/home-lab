#!/usr/bin/env python3
"""create a restic snapshot at an explicit repository"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "recovery" / "fixture"


def configured() -> bool:
    return bool(os.environ.get("RESTIC_REPOSITORY")) and bool(
        os.environ.get("RESTIC_PASSWORD") or os.environ.get("RESTIC_PASSWORD_FILE")
    )


def main() -> int:
    if not configured():
        print("set RESTIC_REPOSITORY and RESTIC_PASSWORD or RESTIC_PASSWORD_FILE", file=sys.stderr)
        return 2

    snapshots = subprocess.run(
        ["restic", "snapshots", "--json"],
        check=False,
        capture_output=True,
        text=True,
    )
    if snapshots.returncode != 0:
        print("restic repository is not initialized; initializing the configured target")
        subprocess.run(["restic", "init"], check=True)

    subprocess.run(
        ["restic", "backup", "--tag", "home-lab-restore-test", str(FIXTURE)],
        check=True,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
