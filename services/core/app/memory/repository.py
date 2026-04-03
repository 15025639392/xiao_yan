from pathlib import Path
import re
from typing import Protocol

from app.memory.models import MemoryEvent


class MemoryRepository(Protocol):
    def save_event(self, event: MemoryEvent) -> None:
        ...

    def list_recent(self, limit: int) -> list[MemoryEvent]:
        ...

    def search_relevant(self, query: str, limit: int) -> list[MemoryEvent]:
        ...


class InMemoryMemoryRepository:
    def __init__(self) -> None:
        self._events: list[MemoryEvent] = []

    def save_event(self, event: MemoryEvent) -> None:
        self._events.append(event)

    def list_recent(self, limit: int) -> list[MemoryEvent]:
        return list(reversed(self._events[-limit:]))

    def search_relevant(self, query: str, limit: int) -> list[MemoryEvent]:
        return _search_relevant_events(self._events, query, limit)


class FileMemoryRepository:
    def __init__(self, storage_path: Path) -> None:
        self.storage_path = storage_path

    def save_event(self, event: MemoryEvent) -> None:
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        with self.storage_path.open("a", encoding="utf-8") as handle:
            handle.write(event.model_dump_json())
            handle.write("\n")

    def list_recent(self, limit: int) -> list[MemoryEvent]:
        if not self.storage_path.exists():
            return []

        events = self._read_all_events()
        events = events[-limit:]
        return list(reversed(events))

    def search_relevant(self, query: str, limit: int) -> list[MemoryEvent]:
        return _search_relevant_events(self._read_all_events(), query, limit)

    def _read_all_events(self) -> list[MemoryEvent]:
        if not self.storage_path.exists():
            return []

        with self.storage_path.open("r", encoding="utf-8") as handle:
            lines = [line.strip() for line in handle.readlines() if line.strip()]

        return [MemoryEvent.model_validate_json(line) for line in lines]


def _search_relevant_events(
    events: list[MemoryEvent],
    query: str,
    limit: int,
) -> list[MemoryEvent]:
    if limit <= 0:
        return []

    query_tokens = _tokenize_text(query)
    scored: list[tuple[int, int, MemoryEvent]] = []

    for index, event in enumerate(events):
        score = _score_event(event, query_tokens)
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


def _score_event(event: MemoryEvent, query_tokens: set[str]) -> int:
    if not query_tokens:
        return 0

    content_tokens = _tokenize_text(event.content)
    overlap = len(query_tokens & content_tokens)
    return overlap


def _tokenize_text(value: str) -> set[str]:
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
