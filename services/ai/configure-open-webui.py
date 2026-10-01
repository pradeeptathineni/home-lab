#!/usr/bin/env python3
"""configure and verify the private llama.cpp connection through supported APIs"""

from __future__ import annotations

import argparse
import json
import os
import urllib.request

LOCAL_BASE_URL = "http://ai-loopback-bridge:18080/v1"


def _request(
    path: str,
    *,
    token: str | None = None,
    payload: dict[str, object] | None = None,
) -> dict[str, object]:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(
        f"http://127.0.0.1:8080{path}",
        data=json.dumps(payload).encode() if payload is not None else None,
        headers=headers,
        method="POST" if payload is not None else "GET",
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        value = json.load(response)
    if not isinstance(value, dict):
        raise RuntimeError(f"Open WebUI returned a non-object for {path}")
    return value


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    args = parser.parse_args()
    authentication = _request(
        "/api/v1/auths/signin",
        payload={
            "email": os.environ["WEBUI_ADMIN_EMAIL"],
            "password": os.environ["WEBUI_ADMIN_PASSWORD"],
        },
    )
    token = authentication.get("token")
    if not isinstance(token, str) or authentication.get("role") != "admin":
        raise RuntimeError("Open WebUI admin authentication failed")
    config = _request("/openai/config", token=token)
    urls = list(config.get("OPENAI_API_BASE_URLS") or [])
    keys = list(config.get("OPENAI_API_KEYS") or [])
    configs = dict(config.get("OPENAI_API_CONFIGS") or {})
    if LOCAL_BASE_URL in urls:
        index = urls.index(LOCAL_BASE_URL)
    else:
        index = len(urls)
        urls.append(LOCAL_BASE_URL)
        keys.append("")
    while len(keys) < len(urls):
        keys.append("")
    configs[str(index)] = {
        "enable": True,
        "auth_type": "none",
        "provider": "llama.cpp",
        "prefix_id": "local",
        "model_ids": [],
        "tags": ["private", "local"],
    }
    _request(
        "/openai/config/update",
        token=token,
        payload={
            "ENABLE_OPENAI_API": True,
            "OPENAI_API_BASE_URLS": urls,
            "OPENAI_API_KEYS": keys,
            "OPENAI_API_CONFIGS": configs,
        },
    )
    exposed_model = f"local.{args.model}"
    models = _request("/openai/models", token=token).get("data")
    if not isinstance(models, list) or exposed_model not in {
        model.get("id") for model in models if isinstance(model, dict)
    }:
        raise RuntimeError(f"Open WebUI did not expose {exposed_model}")
    completion = _request(
        "/openai/chat/completions",
        token=token,
        payload={
            "model": exposed_model,
            "messages": [
                {"role": "user", "content": "Return exactly: private Open WebUI route works"}
            ],
            "temperature": 0,
            "max_tokens": 16,
            "stream": False,
            "chat_template_kwargs": {"enable_thinking": False},
        },
    )
    content = completion.get("choices", [{}])[0].get("message", {}).get("content")
    if content != "private Open WebUI route works":
        raise RuntimeError(f"unexpected local completion: {content!r}")
    print(
        json.dumps(
            {
                "authenticated_admin": True,
                "configured_base_url": LOCAL_BASE_URL,
                "model_visible": exposed_model,
                "completion": content,
                "cloud_api_used": False,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
