from __future__ import annotations

from typing import Any


def extract_model_ids(payload: dict[str, Any]) -> list[str]:
    raw_items = payload.get("data", [])
    if not isinstance(raw_items, list):
        return []

    models: list[str] = []
    seen: set[str] = set()
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        model_id = item.get("id")
        if not isinstance(model_id, str):
            continue
        normalized = model_id.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        models.append(normalized)
    return models
