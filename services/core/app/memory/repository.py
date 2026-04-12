from datetime import datetime, timezone
from typing import Callable
from typing import Literal
from typing import Protocol

from app.memory.models import MemoryEvent
from app.memory.search_utils import (
    search_relevant_events as _search_relevant_events,
)


class MemoryRepository(Protocol):
    def save_event(self, event: MemoryEvent) -> None:
        ...

    def list_recent(
        self,
        limit: int,
        offset: int = 0,
        *,
        status: Literal["active", "deleted", "all"] = "active",
        kind: str | None = None,
        namespace: str | None = None,
        visibility: Literal["internal", "user"] | None = None,
        query: str | None = None,
    ) -> list[MemoryEvent]:
        ...

    def list_recent_chat(self, limit: int, offset: int = 0) -> list[MemoryEvent]:
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

    def soft_delete_event(self, event_id: str) -> bool:
        ...

    def restore_event(self, event_id: str) -> bool:
        ...


class InMemoryMemoryRepository:
    def __init__(self, on_change: Callable[[], None] | None = None) -> None:
        self._events: list[MemoryEvent] = []
        self._on_change = on_change

    def save_event(self, event: MemoryEvent) -> None:
        self._events.append(event)
        self._notify_change()

    def list_recent(
        self,
        limit: int,
        offset: int = 0,
        *,
        status: Literal["active", "deleted", "all"] = "active",
        kind: str | None = None,
        namespace: str | None = None,
        visibility: Literal["internal", "user"] | None = None,
        query: str | None = None,
    ) -> list[MemoryEvent]:
        filtered = _filter_events(
            self._events,
            status=status,
            kind=kind,
            namespace=namespace,
            visibility=visibility,
            query=query,
        )
        return _slice_recent(filtered, limit=limit, offset=offset)

    def list_recent_chat(self, limit: int, offset: int = 0) -> list[MemoryEvent]:
        chat_events = [
            event
            for event in self._events
            if event.deleted_at is None and event.kind == "chat" and event.role in {"user", "assistant"}
        ]
        return _slice_recent(chat_events, limit=limit, offset=offset)

    def search_relevant(self, query: str, limit: int) -> list[MemoryEvent]:
        active_events = [event for event in self._events if event.deleted_at is None]
        return _search_relevant_events(active_events, query, limit)

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
        count = len(self._events)
        if count > 0:
            self._events = []
            self._notify_change()
        return count

    def soft_delete_event(self, event_id: str) -> bool:
        for index, event in enumerate(self._events):
            if event.entry_id != event_id:
                continue
            if event.deleted_at is not None:
                return True
            self._events[index] = event.model_copy(update={"deleted_at": datetime.now(timezone.utc)})
            self._notify_change()
            return True
        return False

    def restore_event(self, event_id: str) -> bool:
        for index, event in enumerate(self._events):
            if event.entry_id != event_id:
                continue
            if event.deleted_at is None:
                return True
            self._events[index] = event.model_copy(update={"deleted_at": None})
            self._notify_change()
            return True
        return False

    def _notify_change(self) -> None:
        if self._on_change is not None:
            self._on_change()


def _slice_recent(events: list[MemoryEvent], *, limit: int, offset: int = 0) -> list[MemoryEvent]:
    if limit <= 0:
        return []

    safe_offset = max(0, offset)
    end = len(events) - safe_offset
    if end <= 0:
        return []

    start = max(0, end - limit)
    return list(reversed(events[start:end]))


def _filter_events(
    events: list[MemoryEvent],
    *,
    status: Literal["active", "deleted", "all"],
    kind: str | None,
    namespace: str | None,
    visibility: Literal["internal", "user"] | None,
    query: str | None,
) -> list[MemoryEvent]:
    normalized_kind = (kind or "").strip().lower()
    normalized_namespace = (namespace or "").strip().lower()
    normalized_query = (query or "").strip().lower()

    filtered: list[MemoryEvent] = []
    for event in events:
        if status == "active" and event.deleted_at is not None:
            continue
        if status == "deleted" and event.deleted_at is None:
            continue
        if normalized_kind and event.kind.strip().lower() != normalized_kind:
            continue
        if normalized_namespace and (event.namespace or "").strip().lower() != normalized_namespace:
            continue
        if visibility is not None and event.visibility != visibility:
            continue
        if normalized_query and normalized_query not in event.content.lower():
            continue
        filtered.append(event)
    return filtered
