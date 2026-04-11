from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from logging import getLogger
from pathlib import Path
from typing import Callable

from app.llm.schemas import ChatMessage

logger = getLogger(__name__)


SearchBackend = Callable[[str, str, int], dict]
WriteBackend = Callable[..., bool]


class MemPalaceAdapter:
    """Bridge for optional MemPalace long-term memory retrieval/write."""

    def __init__(
        self,
        *,
        enabled: bool = True,
        palace_path: str = "~/.mempalace/palace",
        results_limit: int = 3,
        wing: str = "wing_xiaoyan",
        room: str = "chat_exchange",
        search_backend: SearchBackend | None = None,
        write_backend: WriteBackend | None = None,
    ) -> None:
        if not enabled:
            logger.warning("MemPalaceAdapter enabled=False is deprecated and ignored; adapter is always enabled.")
        self.enabled = True
        self.palace_path = str(Path(palace_path).expanduser())
        self.results_limit = max(1, min(10, int(results_limit)))
        self.wing = wing
        self.room = room
        self._search_backend = search_backend
        self._write_backend = write_backend

    def search_context(self, query: str, *, exclude_current_room: bool = False) -> str:
        normalized = (query or "").strip()
        if not normalized:
            return ""

        try:
            payload = self._search(normalized)
        except Exception as exc:  # noqa: BLE001
            logger.warning("MemPalace search failed: %s", exc)
            return ""

        if not isinstance(payload, dict):
            return ""
        if payload.get("error"):
            logger.warning("MemPalace search returned error payload: %s", payload.get("error"))
            return ""

        raw_hits = payload.get("results")
        if not isinstance(raw_hits, list) or not raw_hits:
            return ""

        if exclude_current_room:
            filtered_hits: list[dict] = []
            for raw_hit in raw_hits:
                if not isinstance(raw_hit, dict):
                    continue
                hit_room = str(raw_hit.get("room") or "").strip()
                if hit_room == self.room:
                    continue
                filtered_hits.append(raw_hit)
            raw_hits = filtered_hits
            if not raw_hits:
                return ""

        lines = ["【长期记忆检索】"]
        for raw_hit in raw_hits[: self.results_limit]:
            if not isinstance(raw_hit, dict):
                continue
            text = _compact_text(raw_hit.get("text") or "", 160)
            if not text:
                continue

            hit_wing = str(raw_hit.get("wing") or "unknown")
            hit_room = str(raw_hit.get("room") or "unknown")
            similarity = _format_similarity(raw_hit.get("similarity"))
            lines.append(f"- {hit_wing}/{hit_room} (相似度 {similarity}) {text}")

        return "\n".join(lines) if len(lines) > 1 else ""

    def record_exchange(
        self,
        user_message: str,
        assistant_response: str,
        assistant_session_id: str | None = None,
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
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("MemPalace record exchange failed: %s", exc)
            return False

    def status_snapshot(self) -> dict:
        palace = Path(self.palace_path)
        return {
            "enabled": self.enabled,
            "palace_path": self.palace_path,
            "palace_exists": palace.exists(),
            "dependency_available": _is_mempalace_dependency_available(),
            "results_limit": self.results_limit,
            "wing": self.wing,
            "room": self.room,
        }

    def build_chat_messages(self, user_message: str, *, limit: int) -> list[ChatMessage]:
        normalized = (user_message or "").strip()
        if not normalized:
            return []

        # Treat limit as a turn baseline instead of a raw event count.
        # This keeps enough nearby dialogue while bounding prompt growth.
        turn_limit = max(1, int(limit))
        max_history_messages = turn_limit * 2
        candidate_limit = min(120, max(max_history_messages * 4, 12))
        token_budget = max(400, min(8000, turn_limit * 300))

        recent = self.list_recent_chat_messages(limit=candidate_limit, offset=0)
        selected_latest_first: list[dict] = []
        consumed_tokens = 0
        for item in recent:
            if len(selected_latest_first) >= max_history_messages:
                break

            message_text = str(item.get("content") or "")
            message_tokens = _estimate_tokens(message_text)
            if selected_latest_first and consumed_tokens + message_tokens > token_budget:
                break

            selected_latest_first.append(item)
            consumed_tokens += message_tokens

        ordered_history = list(reversed(selected_latest_first))
        messages = [ChatMessage(role=item["role"], content=item["content"]) for item in ordered_history]
        messages.append(ChatMessage(role="user", content=normalized))
        return messages

    def list_recent_chat_messages(self, *, limit: int, offset: int = 0) -> list[dict]:
        safe_limit = max(0, int(limit))
        if safe_limit == 0:
            return []

        safe_offset = max(0, int(offset))
        events = self._list_chat_events()
        if not events:
            return []

        end = len(events) - safe_offset
        if end <= 0:
            return []

        start = max(0, end - safe_limit)
        return list(reversed(events[start:end]))

    def _search(self, query: str) -> dict:
        if self._search_backend is not None:
            return self._search_backend(query, self.palace_path, self.results_limit)

        from mempalace.searcher import search_memories

        return search_memories(
            query,
            palace_path=self.palace_path,
            n_results=self.results_limit,
        )

    def _write(
        self,
        *,
        content: str,
        source_context: str,
        session_id: str | None,
    ) -> bool:
        if self._write_backend is not None:
            return bool(
                self._write_backend(
                    content=content,
                    source_context=source_context,
                    session_id=session_id,
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
                }
            ],
        )
        return True

    def _list_chat_events(self) -> list[dict]:
        collection = self._get_collection(create=False)
        if collection is None:
            return []

        try:
            payload = collection.get(
                where={"$and": [{"wing": self.wing}, {"room": self.room}]},
                include=["documents", "metadatas"],
                limit=10000,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("MemPalace list chat events failed: %s", exc)
            return []

        documents = payload.get("documents") or []
        metadatas = payload.get("metadatas") or []
        ids = payload.get("ids") or []

        rows: list[tuple[str, str, str, str, str | None]] = []
        for index, raw_document in enumerate(documents):
            if not isinstance(raw_document, str):
                continue
            metadata = metadatas[index] if index < len(metadatas) and isinstance(metadatas[index], dict) else {}
            drawer_id = ids[index] if index < len(ids) and isinstance(ids[index], str) else f"row_{index}"
            filed_at = str(metadata.get("filed_at") or "")
            raw_session_id = metadata.get("session_id")
            session_id = str(raw_session_id).strip() if raw_session_id is not None else ""
            normalized_session_id = session_id or None

            user_text, assistant_text = _parse_exchange_document(raw_document)
            if user_text:
                rows.append((filed_at, drawer_id, "user", user_text, normalized_session_id))
            if assistant_text:
                rows.append((filed_at, drawer_id, "assistant", assistant_text, normalized_session_id))

            if not user_text and not assistant_text:
                compact = " ".join(raw_document.split())
                if compact:
                    rows.append((filed_at, drawer_id, "assistant", compact, normalized_session_id))

        rows.sort(key=lambda item: item[0])
        events: list[dict] = []
        for filed_at, drawer_id, role, content, session_id in rows:
            message_id = f"{drawer_id}:{role}:{len(events)}"
            events.append(
                {
                    "id": message_id,
                    "role": role,
                    "content": content,
                    "created_at": filed_at or None,
                    "session_id": session_id,
                }
            )
        return events

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


def _compact_text(text: str, limit: int) -> str:
    compacted = " ".join(text.split())
    if len(compacted) <= limit:
        return compacted
    return f"{compacted[: limit - 1].rstrip()}…"


def _format_similarity(value) -> str:
    try:
        score = float(value)
    except (TypeError, ValueError):
        return "?"
    return f"{score:.2f}"


def _is_mempalace_dependency_available() -> bool:
    try:
        import mempalace  # noqa: F401
    except Exception:  # noqa: BLE001
        return False
    return True


def _estimate_tokens(text: str) -> int:
    compact = " ".join((text or "").split())
    if not compact:
        return 1
    # Rough estimate for mixed CJK/English text.
    return max(1, int(len(compact) / 1.8))


def _parse_exchange_document(document: str) -> tuple[str, str]:
    lines = [line.rstrip() for line in document.splitlines()]
    if not lines:
        return "", ""

    first = lines[0].strip()
    if first.startswith(">"):
        user = first[1:].strip()
        assistant = "\n".join(line for line in lines[1:] if line.strip()).strip()
        return user, assistant

    return "", " ".join(line for line in lines if line.strip()).strip()
