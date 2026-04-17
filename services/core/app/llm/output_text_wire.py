from __future__ import annotations

from typing import Any


def collect_output_message_texts(output_items: object) -> str:
    if not isinstance(output_items, list):
        return ""

    segments: list[str] = []
    for item in output_items:
        if not isinstance(item, dict) or item.get("type") != "message":
            continue
        content_items = item.get("content", [])
        if not isinstance(content_items, list):
            continue
        for content_item in content_items:
            if not isinstance(content_item, dict):
                continue
            text = content_item.get("text")
            if content_item.get("type") in {"output_text", "text"} and isinstance(text, str) and text:
                segments.append(text)
    return "".join(segments)
