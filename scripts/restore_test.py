#!/usr/bin/env python3
"""restore a known snapshot into scratch and compare its checksum"""

from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = ROOT / "recovery" / "fixture" / "expected.txt"


def configured() -> bool:
    return bool(os.environ.get("RESTIC_REPOSITORY")) and bool(
        os.environ.get("RESTIC_PASSWORD") or os.environ.get("RESTIC_PASSWORD_FILE")
    )


def _is_local_repository(value: str) -> bool:
    parsed = urlparse(value)
    return not parsed.scheme or parsed.scheme == "file"


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--allow-local-repository",
        action="store_true",
        help="acknowledge that a local repository proves mechanics, not resilience",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not configured():
        print("set RESTIC_REPOSITORY and RESTIC_PASSWORD or RESTIC_PASSWORD_FILE", file=sys.stderr)
        return 2
    repository = os.environ["RESTIC_REPOSITORY"]
    # local repositories prove mechanics but not loss resilience
    if _is_local_repository(repository) and not args.allow_local_repository:
        print("local restic repository requires --allow-local-repository", file=sys.stderr)
        return 2

    scratch = Path(tempfile.mkdtemp(prefix="home-lab-restore-"))
    print(f"restore scratch: {scratch}", flush=True)
    try:
        subprocess.run(
            [
                "restic",
                "restore",
                "latest",
                "--tag",
                "home-lab-restore-test",
                "--target",
                str(scratch),
            ],
            check=True,
        )
        matches = list(scratch.rglob("expected.txt"))
        if len(matches) != 1 or _digest(matches[0]) != _digest(EXPECTED):
            print("restore checksum mismatch; scratch preserved", file=sys.stderr)
            return 1
        print(f"restore verified: sha256={_digest(EXPECTED)}")
    except subprocess.CalledProcessError:
        print("restore failed; scratch preserved", file=sys.stderr)
        return 1
    shutil.rmtree(scratch)
    print("verified scratch removed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
