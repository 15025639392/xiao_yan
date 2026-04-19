from __future__ import annotations

import json


def compact_text(text: str, limit: int) -> str:
    compacted = " ".join(text.split())
    if len(compacted) <= limit:
        return compacted
    return f"{compacted[: limit - 1].rstrip()}…"


def encode_reasoning_state(value: dict | None) -> str:
    if not isinstance(value, dict):
        return ""
    try:
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    except Exception:  # noqa: BLE001
        return ""


def parse_reasoning_state(value) -> dict | None:
    if isinstance(value, dict):
        return value
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    if not normalized:
        return None
    try:
        parsed = json.loads(normalized)
    except Exception:  # noqa: BLE001
        return None
    return parsed if isinstance(parsed, dict) else None


def format_similarity(value) -> str:
    try:
        score = float(value)
    except (TypeError, ValueError):
        return "?"
    return f"{score:.2f}"


def estimate_tokens(text: str) -> int:
    compact = " ".join((text or "").split())
    if not compact:
        return 1
    # Rough estimate for mixed CJK/English text.
    return max(1, int(len(compact) / 1.8))


def clamp_weight(value: float, *, fallback: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return fallback
    return max(0.0, min(1.0, parsed))


def parse_exchange_document(document: str) -> tuple[str, str]:
    lines = [line.rstrip() for line in document.splitlines()]
    if not lines:
        return "", ""

    first = lines[0].strip()
    if first.startswith(">"):
        user = first[1:].strip()
        assistant = "\n".join(line for line in lines[1:] if line.strip()).strip()
        return user, assistant

    return "", " ".join(line for line in lines if line.strip()).strip()
