import json
from pathlib import Path
import re
from typing import Protocol

from app.memory.models import MemoryEvent
from pydantic import ValidationError


class MemoryRepository(Protocol):
    def save_event(self, event: MemoryEvent) -> None:
        ...

    def list_recent(self, limit: int) -> list[MemoryEvent]:
        ...

    def search_relevant(self, query: str, limit: int) -> list[MemoryEvent]:
        ...

    def delete_event(self, event_id: str) -> bool:
        """删除指定 ID 的记忆事件，返回是否成功"""
        ...

    def update_event(self, event_id: str, **kwargs) -> bool:
        """更新指定 ID 的记忆事件的字段，返回是否成功"""
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

    def delete_event(self, event_id: str) -> bool:
        """通过 entry_id 匹配删除"""
        original_len = len(self._events)
        self._events = [e for e in self._events if e.entry_id != event_id]
        return len(self._events) < original_len

    def update_event(self, event_id: str, **kwargs) -> bool:
        """更新事件 — 通过 entry_id 精确匹配"""
        for i, e in enumerate(self._events):
            if e.entry_id == event_id:
                updated = e.model_copy(update=kwargs)
                self._events[i] = updated
                return True
        return False


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

    def delete_event(self, event_id: str) -> bool:
        """通过重写文件删除指定 ID 的记忆事件

        event_id 是 MemoryEntry.id（如 mem_20260405123456_1a），
        通过 MemoryEvent.entry_id 字段进行精确匹配。
        """
        if not self.storage_path.exists():
            return False

        events = self._read_all_events()

        # 通过 entry_id 精确匹配
        filtered = []
        deleted = False
        for e in events:
            if not deleted and e.entry_id == event_id:
                deleted = True
                continue
            filtered.append(e)

        if deleted:
            self._write_all_events(filtered)

        return deleted

    def update_event(self, event_id: str, **kwargs) -> bool:
        """更新指定 ID 的事件字段，通过重写文件实现"""
        if not self.storage_path.exists():
            return False

        events = self._read_all_events()
        updated = False

        for i, e in enumerate(events):
            # 通过 entry_id 精确匹配
            if not updated and e.entry_id == event_id:
                events[i] = e.model_copy(update=kwargs)
                updated = True
                break

        if updated:
            self._write_all_events(events)

        return updated

    def _read_all_events(self) -> list[MemoryEvent]:
        if not self.storage_path.exists():
            return []

        with self.storage_path.open("r", encoding="utf-8") as handle:
            lines = [line.strip() for line in handle.readlines() if line.strip()]

        events: list[MemoryEvent] = []
        seen_entry_ids: set[str] = set()
        needs_rewrite = False

        for line in lines:
            try:
                payload = json.loads(line)
                event = MemoryEvent.model_validate(payload)
            except (json.JSONDecodeError, ValidationError):
                needs_rewrite = True
                continue

            if event.entry_id in seen_entry_ids:
                needs_rewrite = True
                continue

            seen_entry_ids.add(event.entry_id)
            events.append(event)

        if needs_rewrite:
            self._write_all_events(events)

        return events

    def _write_all_events(self, events: list[MemoryEvent]) -> None:
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        with self.storage_path.open("w", encoding="utf-8") as handle:
            for event in events:
                handle.write(event.model_dump_json())
                handle.write("\n")


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
