import json
from pathlib import Path
from typing import Callable
from typing import Protocol

from app.memory.models import MemoryEvent
from app.memory.search_utils import (
    score_event as _score_event,
    search_relevant_events as _search_relevant_events,
    tokenize_text as _tokenize_text,
)
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

    def clear_all(self) -> int:
        """清空所有记忆事件，返回已清除的数量"""
        ...


class InMemoryMemoryRepository:
    def __init__(self, on_change: Callable[[], None] | None = None) -> None:
        self._events: list[MemoryEvent] = []
        self._on_change = on_change

    def save_event(self, event: MemoryEvent) -> None:
        self._events.append(event)
        self._notify_change()

    def list_recent(self, limit: int) -> list[MemoryEvent]:
        return list(reversed(self._events[-limit:]))

    def search_relevant(self, query: str, limit: int) -> list[MemoryEvent]:
        return _search_relevant_events(self._events, query, limit)

    def delete_event(self, event_id: str) -> bool:
        """通过 entry_id 匹配删除"""
        original_len = len(self._events)
        self._events = [e for e in self._events if e.entry_id != event_id]
        deleted = len(self._events) < original_len
        if deleted:
            self._notify_change()
        return deleted

    def update_event(self, event_id: str, **kwargs) -> bool:
        """更新事件 — 通过 entry_id 精确匹配"""
        for i, e in enumerate(self._events):
            if e.entry_id == event_id:
                updated = e.model_copy(update=kwargs)
                self._events[i] = updated
                self._notify_change()
                return True
        return False

    def set_on_change_callback(self, callback: Callable[[], None] | None) -> None:
        self._on_change = callback

    def clear_all(self) -> int:
        """清空所有记忆事件，返回已清除的数量"""
        if not self.storage_path.exists():
            return 0

        events = self._read_all_events()
        count = len(events)

        if count > 0:
            self.storage_path.write_text("", encoding="utf-8")
            self._notify_change()

        return count

    def _notify_change(self) -> None:
        if self._on_change is not None:
            self._on_change()


class FileMemoryRepository:
    def __init__(self, storage_path: Path, on_change: Callable[[], None] | None = None) -> None:
        self.storage_path = storage_path
        self._on_change = on_change

    def save_event(self, event: MemoryEvent) -> None:
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        with self.storage_path.open("a", encoding="utf-8") as handle:
            handle.write(event.model_dump_json())
            handle.write("\n")
        self._notify_change()

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
            self._notify_change()

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
            self._notify_change()

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

    def set_on_change_callback(self, callback: Callable[[], None] | None) -> None:
        self._on_change = callback

    def clear_all(self) -> int:
        """清空所有记忆事件，返回已清除的数量"""
        if not self.storage_path.exists():
            return 0

        events = self._read_all_events()
        count = len(events)

        if count > 0:
            self.storage_path.write_text("", encoding="utf-8")
            self._notify_change()

        return count

    def _notify_change(self) -> None:
        if self._on_change is not None:
            self._on_change()
