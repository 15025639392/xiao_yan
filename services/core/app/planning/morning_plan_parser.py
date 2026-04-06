from __future__ import annotations

import json
import re


def parse_draft_steps(output_text: str) -> list[dict] | None:
    for candidate in draft_json_candidates(output_text):
        try:
            data = json.loads(candidate)
        except json.JSONDecodeError:
            continue

        if isinstance(data, dict):
            steps = data.get("steps")
            return steps if isinstance(steps, list) else None

        if isinstance(data, list):
            return data

    return None


def draft_json_candidates(output_text: str) -> list[str]:
    text = output_text.strip()
    if not text:
        return []

    candidates: list[str] = [text]

    fenced_blocks = re.findall(r"```(?:json)?\s*(.*?)```", text, flags=re.IGNORECASE | re.DOTALL)
    candidates.extend(block.strip() for block in fenced_blocks if block.strip())

    for opener, closer in (("{", "}"), ("[", "]")):
        start = text.find(opener)
        end = text.rfind(closer)
        if start != -1 and end != -1 and start < end:
            snippet = text[start : end + 1].strip()
            if snippet and snippet not in candidates:
                candidates.append(snippet)

    return candidates


__all__ = [
    "parse_draft_steps",
    "draft_json_candidates",
]
