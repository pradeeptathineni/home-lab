#!/usr/bin/env python3
"""ingest and find the synthetic paperless fixture"""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path

import requests

BASE_URL = "http://127.0.0.1:8000"
FIXTURE = Path("/opt/home-lab/fixtures/synthetic-home-lab-note.txt")
MARKER = "cedar-meteor-3921"


def _token() -> str:
    response = requests.post(
        f"{BASE_URL}/api/token/",
        data={
            "username": os.environ["PAPERLESS_ADMIN_USER"],
            "password": os.environ["PAPERLESS_ADMIN_PASSWORD"],
        },
        timeout=15,
    )
    response.raise_for_status()
    return response.json()["token"]


def _find(headers: dict[str, str]) -> list[dict[str, object]]:
    response = requests.get(
        f"{BASE_URL}/api/documents/",
        headers=headers,
        params={"query": MARKER},
        timeout=15,
    )
    response.raise_for_status()
    return response.json()["results"]


def main() -> None:
    payload = FIXTURE.read_bytes()
    headers = {"Authorization": f"Token {_token()}"}
    matches = _find(headers)
    task_id = None
    if not matches:
        response = requests.post(
            f"{BASE_URL}/api/documents/post_document/",
            headers=headers,
            files={"document": (FIXTURE.name, payload, "text/plain")},
            data={"title": "Synthetic Home Lab Note"},
            timeout=30,
        )
        response.raise_for_status()
        task_id = response.json()
        # the searchable marker is the proof boundary, not queue completion
        for _ in range(30):
            time.sleep(2)
            matches = _find(headers)
            if matches:
                break
    if not matches:
        raise RuntimeError("fixture did not become searchable")
    print(
        json.dumps(
            {
                "fixture": FIXTURE.name,
                "sha256": hashlib.sha256(payload).hexdigest(),
                "marker": MARKER,
                "task_id": task_id,
                "document_id": matches[0]["id"],
                "query_hit": True,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
