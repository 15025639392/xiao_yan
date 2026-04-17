from __future__ import annotations

import httpx

from app.llm.model_wire import extract_model_ids


def build_auth_headers(api_key: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }


def fetch_model_ids(
    *,
    client: httpx.Client,
    base_url: str,
    headers: dict[str, str],
) -> list[str]:
    response = client.get(
        f"{base_url}/models",
        headers=headers,
    )
    response.raise_for_status()
    return extract_model_ids(response.json())
