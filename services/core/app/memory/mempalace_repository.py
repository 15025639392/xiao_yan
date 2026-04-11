from __future__ import annotations

import json
from logging import getLogger
from pathlib import Path
from typing import Callable

from app.memory.models import MemoryEvent
from app.memory.repository import _slice_recent
from app.memory.search_utils import search_relevant_events as _search_relevant_events

logger = getLogger(__name__)

class MemPalaceMemoryRepository:
    """MemoryRepository implementation backed by MemPalace/Chroma.

    This repository persists structured memory events into the same MemPalace
    palace used by chat exchange storage, but in a dedicated room.
    """

    def __init__(
        self,
        *,
        palace_path: str,
        wing: str,
        room: str,
        chat_room: str | None = None,
        on_change: Callable[[], None] | None = None,
    ) -> None:
        self.palace_path = str(Path(palace_path).expanduser())
        self.wing = wing
        self.room = room
        self.chat_room = chat_room
        self._on_change = on_change
        self._fallback_events: dict[str, MemoryEvent] = {}

    def save_event(self, event: MemoryEvent) -> None:
        collection = self._get_collection(create=True)
        if collection is None:
            self._fallback_events[event.entry_id] = event
            self._notify_change()
            return

        doc_id = self._doc_id(event.entry_id)
        payload = event.model_dump_json()
        metadata = self._build_metadata(event)

        collection.upsert(
            ids=[doc_id],
            documents=[payload],
            metadatas=[metadata],
        )
        self._notify_change()

    def list_recent(self, limit: int, offset: int = 0) -> list[MemoryEvent]:
        events = self._read_all_events()
        return _slice_recent(events, limit=limit, offset=offset)

    def list_recent_chat(self, limit: int, offset: int = 0) -> list[MemoryEvent]:
        chat_events = [
            event for event in self._read_all_events() if event.kind == "chat" and event.role in {"user", "assistant"}
        ]
        return _slice_recent(chat_events, limit=limit, offset=offset)

    def search_relevant(self, query: str, limit: int) -> list[MemoryEvent]:
        return _search_relevant_events(self._read_all_events(), query, limit)

    def delete_event(self, event_id: str) -> bool:
        collection = self._get_collection(create=False)
        if collection is None:
            deleted = self._fallback_events.pop(event_id, None) is not None
            if deleted:
                self._notify_change()
            return deleted

        doc_id = self._doc_id(event_id)
        existing = collection.get(ids=[doc_id], include=[])
        ids = existing.get("ids") or []
        if not ids:
            return False

        collection.delete(ids=[doc_id])
        self._notify_change()
        return True

    def update_event(self, event_id: str, **kwargs) -> bool:
        collection = self._get_collection(create=False)
        if collection is None:
            current = self._fallback_events.get(event_id)
            if current is None:
                return False
            self._fallback_events[event_id] = current.model_copy(update=kwargs)
            self._notify_change()
            return True

        doc_id = self._doc_id(event_id)
        payload = collection.get(ids=[doc_id], include=["documents"])
        docs = payload.get("documents") or []
        if not docs:
            return False

        raw = docs[0]
        if not isinstance(raw, str):
            return False

        try:
            event = MemoryEvent.model_validate(json.loads(raw))
        except Exception:  # noqa: BLE001
            return False

        updated = event.model_copy(update=kwargs)
        collection.upsert(
            ids=[doc_id],
            documents=[updated.model_dump_json()],
            metadatas=[self._build_metadata(updated)],
        )
        self._notify_change()
        return True

    def clear_all(self) -> int:
        collection = self._get_collection(create=False)
        if collection is None:
            count = len(self._fallback_events)
            if count:
                self._fallback_events.clear()
                self._notify_change()
            return count

        event_payload = collection.get(where=self._where_filter(), include=[])
        event_ids = [doc_id for doc_id in (event_payload.get("ids") or []) if isinstance(doc_id, str)]

        chat_ids: list[str] = []
        if self.chat_room:
            chat_payload = collection.get(where=self._chat_room_filter(), include=[])
            chat_ids = [doc_id for doc_id in (chat_payload.get("ids") or []) if isinstance(doc_id, str)]

        ids = sorted(set(event_ids + chat_ids))
        if not ids:
            return 0

        collection.delete(ids=ids)
        self._notify_change()
        return len(ids)

    def set_on_change_callback(self, callback: Callable[[], None] | None) -> None:
        self._on_change = callback

    def _read_all_events(self) -> list[MemoryEvent]:
        collection = self._get_collection(create=False)
        if collection is None:
            return sorted(self._fallback_events.values(), key=lambda event: event.created_at)

        payload = collection.get(
            where=self._where_filter(),
            include=["documents"],
            limit=100000,
        )
        docs = payload.get("documents") or []
        ids = payload.get("ids") or []

        parsed: list[MemoryEvent] = []
        for index, raw_doc in enumerate(docs):
            if not isinstance(raw_doc, str):
                continue

            try:
                event = MemoryEvent.model_validate(json.loads(raw_doc))
            except Exception:  # noqa: BLE001
                continue

            if index < len(ids) and isinstance(ids[index], str):
                expected_doc_id = self._doc_id(event.entry_id)
                if ids[index] != expected_doc_id:
                    continue
            parsed.append(event)

        parsed.sort(key=lambda event: event.created_at)
        return parsed

    def _build_metadata(self, event: MemoryEvent) -> dict[str, str]:
        return {
            "namespace": "memory_event",
            "wing": self.wing,
            "room": self.room,
            "entry_id": event.entry_id,
            "kind": event.kind,
            "role": event.role or "",
            "session_id": event.session_id or "",
            "source_context": event.source_context or "",
            "created_at": event.created_at.isoformat(),
        }

    def _where_filter(self) -> dict:
        return {
            "$and": [
                {"namespace": "memory_event"},
                {"wing": self.wing},
                {"room": self.room},
            ]
        }

    def _chat_room_filter(self) -> dict:
        return {
            "$and": [
                {"wing": self.wing},
                {"room": self.chat_room},
            ]
        }

    @staticmethod
    def _doc_id(entry_id: str) -> str:
        return f"memory_event:{entry_id}"

    def _get_collection(self, *, create: bool):
        try:
            import chromadb
            from mempalace.config import MempalaceConfig
        except Exception as exc:  # noqa: BLE001
            logger.warning("MemPalace dependencies unavailable, falling back to in-memory repository: %s", exc)
            return None

        try:
            config = MempalaceConfig()
            client = chromadb.PersistentClient(path=self.palace_path)
            if create:
                return client.get_or_create_collection(config.collection_name)
            return client.get_collection(config.collection_name)
        except Exception as exc:  # noqa: BLE001
            logger.warning("MemPalace collection open failed, falling back to in-memory repository: %s", exc)
            return None

    def _notify_change(self) -> None:
        if self._on_change is not None:
            self._on_change()
