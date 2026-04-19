from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from logging import getLogger
from pathlib import Path
from typing import Callable

from app.llm.schemas import ChatMessage
from app.memory.mempalace_chat_history import (
    build_chat_messages as build_recent_chat_messages,
    list_chat_events,
    list_recent_chat_messages as load_recent_chat_messages,
)
from app.memory.mempalace_payloads import (
    encode_reasoning_state,
)
from app.memory.mempalace_search import has_cross_room_long_term_sources, search_context

logger = getLogger(__name__)


SearchBackend = Callable[[str, str, int], dict]
WriteBackend = Callable[..., bool]


class MemPalaceAdapter:
    """Bridge for optional MemPalace long-term memory retrieval/write."""

    def __init__(
        self,
        *,
        palace_path: str = str(Path(__file__).resolve().parents[2] / ".mempalace" / "palace"),
        results_limit: int = 3,
        wing: str = "wing_xiaoyan",
        room: str = "chat_exchange",
        search_backend: SearchBackend | None = None,
        write_backend: WriteBackend | None = None,
    ) -> None:
        self.palace_path = str(Path(palace_path).expanduser())
        self.results_limit = max(1, min(10, int(results_limit)))
        self.wing = wing
        self.room = room
        self._search_backend = search_backend
        self._write_backend = write_backend
        self._cross_room_scan_cached_at: datetime | None = None
        self._cross_room_scan_result: bool = False

    def search_context(
        self,
        query: str,
        *,
        exclude_current_room: bool = False,
        max_hits: int | None = None,
        retrieval_weight: float | None = None,
    ) -> str:
        return search_context(
            query,
            room=self.room,
            palace_path=self.palace_path,
            results_limit=self.results_limit,
            search_backend=lambda search_query, search_palace_path, search_limit: self._search(
                search_query,
                limit=search_limit,
            ),
            exclude_current_room=exclude_current_room,
            max_hits=max_hits,
            retrieval_weight=retrieval_weight,
        )

    def record_exchange(
        self,
        user_message: str,
        assistant_response: str,
        assistant_session_id: str | None = None,
        request_key: str | None = None,
        reasoning_session_id: str | None = None,
        reasoning_state: dict | None = None,
    ) -> bool:
        user_text = (user_message or "").strip()
        assistant_text = (assistant_response or "").strip()
        if not user_text or not assistant_text:
            return False

        content = f"> {user_text}\n{assistant_text}"
        source_context = "xiaoyan_chat_exchange"

        try:
            return self._write(
                content=content,
                source_context=source_context,
                session_id=assistant_session_id,
                request_key=request_key,
                reasoning_session_id=reasoning_session_id,
                reasoning_state=reasoning_state,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("MemPalace record exchange failed: %s", exc)
            return False

    def status_snapshot(self) -> dict:
        palace = Path(self.palace_path)
        return {
            "palace_path": self.palace_path,
            "palace_exists": palace.exists(),
            "dependency_available": _is_mempalace_dependency_available(),
            "results_limit": self.results_limit,
            "wing": self.wing,
            "room": self.room,
        }

    def build_chat_messages(self, user_message: str, *, limit: int, recent_weight: float | None = None) -> list[ChatMessage]:
        return build_recent_chat_messages(
            user_message,
            limit=limit,
            recent_weight=recent_weight,
            recent_loader=lambda recent_limit, recent_offset: self.list_recent_chat_messages(
                limit=recent_limit,
                offset=recent_offset,
            ),
        )

    def list_recent_chat_messages(self, *, limit: int, offset: int = 0) -> list[dict]:
        return load_recent_chat_messages(
            limit=limit,
            offset=offset,
            event_loader=lambda event_limit: self._list_chat_events(limit=event_limit),
        )

    def _search(self, query: str, *, limit: int) -> dict:
        if self._search_backend is not None:
            return self._search_backend(query, self.palace_path, limit)

        from mempalace.searcher import search_memories

        return search_memories(
            query,
            palace_path=self.palace_path,
            n_results=limit,
        )

    def has_cross_room_long_term_sources(self, *, cache_seconds: int = 30) -> bool:
        """Returns whether non-current-room long-term sources are available.

        We intentionally ignore the mirrored event room (`*_events`) because it is
        operational chat mirroring data, not curated long-term memory.
        """

        has_sources, cached_at, cached_result = has_cross_room_long_term_sources(
            wing=self.wing,
            room=self.room,
            get_collection=lambda create: self._get_collection(create=create),
            cached_at=self._cross_room_scan_cached_at,
            cached_result=self._cross_room_scan_result,
            cache_seconds=cache_seconds,
        )
        self._cross_room_scan_cached_at = cached_at
        self._cross_room_scan_result = cached_result
        return has_sources

    def _write(
        self,
        *,
        content: str,
        source_context: str,
        session_id: str | None,
        request_key: str | None,
        reasoning_session_id: str | None,
        reasoning_state: dict | None,
    ) -> bool:
        if self._write_backend is not None:
            return bool(
                self._write_backend(
                    content=content,
                    source_context=source_context,
                    session_id=session_id,
                    request_key=request_key,
                    reasoning_session_id=reasoning_session_id,
                    reasoning_state=reasoning_state,
                )
            )

        import chromadb
        from mempalace.config import MempalaceConfig

        config = MempalaceConfig()
        collection_name = config.collection_name
        client = chromadb.PersistentClient(path=self.palace_path)
        collection = client.get_or_create_collection(collection_name)

        now = datetime.now(timezone.utc)
        digest = hashlib.sha256(f"{session_id or ''}:{content}".encode("utf-8")).hexdigest()[:24]
        drawer_id = f"drawer_{self.wing}_{self.room}_{digest}"

        collection.upsert(
            ids=[drawer_id],
            documents=[content],
            metadatas=[
                {
                    "wing": self.wing,
                    "room": self.room,
                    "source_file": source_context,
                    "chunk_index": 0,
                    "added_by": "xiaoyan",
                    "filed_at": now.isoformat(),
                    "session_id": session_id or "",
                    "request_key": (request_key or "").strip(),
                    "reasoning_session_id": (reasoning_session_id or "").strip(),
                    "reasoning_state": encode_reasoning_state(reasoning_state),
                }
            ],
        )
        return True

    def _list_chat_events(self, *, limit: int = 10000) -> list[dict]:
        return list_chat_events(
            wing=self.wing,
            room=self.room,
            limit=limit,
            get_collection=lambda create: self._get_collection(create=create),
        )

    def _get_collection(self, *, create: bool):
        try:
            import chromadb
            from mempalace.config import MempalaceConfig
        except Exception as exc:  # noqa: BLE001
            logger.warning("MemPalace dependency unavailable: %s", exc)
            return None

        try:
            config = MempalaceConfig()
            client = chromadb.PersistentClient(path=self.palace_path)
            if create:
                return client.get_or_create_collection(config.collection_name)
            return client.get_collection(config.collection_name)
        except Exception as exc:  # noqa: BLE001
            logger.warning("MemPalace open collection failed: %s", exc)
            return None

def _is_mempalace_dependency_available() -> bool:
    try:
        import mempalace  # noqa: F401
    except Exception:  # noqa: BLE001
        return False
    return True
