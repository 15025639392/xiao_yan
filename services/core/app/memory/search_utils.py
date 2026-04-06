from __future__ import annotations

import re

from app.memory.models import MemoryEvent


def search_relevant_events(
    events: list[MemoryEvent],
    query: str,
    limit: int,
) -> list[MemoryEvent]:
    if limit <= 0:
        return []

    query_tokens = tokenize_text(query)
    scored: list[tuple[int, int, MemoryEvent]] = []

    for index, event in enumerate(events):
        score = score_event(event, query_tokens)
        scored.append((score, index, event))

    positive_matches = [item for item in scored if item[0] > 0]
    if not positive_matches:
        return events[-limit:]

    positive_matches.sort(key=lambda item: (item[0], item[1]), reverse=True)
    selected_indexes: set[int] = set()

    for _, index, _ in positive_matches:
        if len(selected_indexes) >= limit:
            break

        selected_indexes.add(index)
        if len(selected_indexes) >= limit:
            break

        for neighbor in (index - 1, index + 1):
            if 0 <= neighbor < len(events):
                selected_indexes.add(neighbor)
            if len(selected_indexes) >= limit:
                break

    if len(selected_indexes) < limit:
        for fallback_index in range(len(events) - 1, -1, -1):
            selected_indexes.add(fallback_index)
            if len(selected_indexes) >= limit:
                break

    selected = [events[index] for index in sorted(selected_indexes)[:limit]]
    selected.sort(key=lambda event: event.created_at)
    return selected


def score_event(event: MemoryEvent, query_tokens: set[str]) -> int:
    if not query_tokens:
        return 0

    content_tokens = tokenize_text(event.content)
    overlap = len(query_tokens & content_tokens)
    return overlap


def tokenize_text(value: str) -> set[str]:
    tokens: set[str] = set()

    ascii_words = re.findall(r"[A-Za-z0-9_]+", value.lower())
    tokens.update(word for word in ascii_words if word)

    cjk_chunks = re.findall(r"[\u4e00-\u9fff]+", value)
    for chunk in cjk_chunks:
        if len(chunk) == 1:
            tokens.add(chunk)
            continue

        tokens.update(chunk[index : index + 2] for index in range(len(chunk) - 1))
        tokens.update(chunk)

    return tokens


__all__ = [
    "search_relevant_events",
    "score_event",
    "tokenize_text",
]
