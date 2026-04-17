from __future__ import annotations

from datetime import datetime, timezone
from logging import getLogger
from typing import Protocol

from app.llm.schemas import ChatMessage
from app.memory.models import MemoryEvent
from app.memory.repository import MemoryRepository
from app.memory.search_utils import tokenize_text

logger = getLogger(__name__)

RECENT_CONTEXT_WEIGHT = 0.7
LONG_TERM_CONTEXT_WEIGHT = 0.3


class ChatMemoryBackend(Protocol):
    def search_context(
        self,
        query: str,
        *,
        exclude_current_room: bool = False,
        max_hits: int | None = None,
        retrieval_weight: float | None = None,
    ) -> str:
        ...

    def has_cross_room_long_term_sources(self, *, cache_seconds: int = 30) -> bool:
        ...

    def build_chat_messages(self, user_message: str, *, limit: int) -> list[ChatMessage]:
        ...

    def list_recent_chat_messages(self, *, limit: int, offset: int = 0) -> list[dict]:
        ...

    def record_exchange(
        self,
        user_message: str,
        assistant_response: str,
        assistant_session_id: str | None = None,
        reasoning_session_id: str | None = None,
        reasoning_state: dict | None = None,
    ) -> bool:
        ...


class ChatMemoryRuntime:
    """Composes chat-specific memory retrieval/write behind a memory-layer boundary."""

    def __init__(self, *, backend: ChatMemoryBackend, repository: MemoryRepository) -> None:
        self.backend = backend
        self.repository = repository

    def resolve_context(self, *, user_message: str, context_limit: int) -> tuple[list[ChatMessage], str, bool, bool]:
        recent_turn_limit, long_term_hits = _split_context_budget(context_limit)
        memory_context = ""
        search_failed = False
        retrieval_attempted = False
        should_search_cross_room = True

        try:
            should_search_cross_room = bool(self.backend.has_cross_room_long_term_sources())
        except Exception as exc:  # noqa: BLE001
            logger.warning("Chat memory cross-room probe raised unexpectedly: %s", exc)
            should_search_cross_room = True

        try:
            if should_search_cross_room:
                retrieval_attempted = True
                memory_context = self.backend.search_context(
                    user_message,
                    exclude_current_room=True,
                    max_hits=long_term_hits,
                    retrieval_weight=LONG_TERM_CONTEXT_WEIGHT,
                )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Chat memory search_context raised unexpectedly: %s", exc)
            memory_context = ""
            search_failed = True

        try:
            chat_messages = self.backend.build_chat_messages(
                user_message,
                limit=recent_turn_limit,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Chat memory build_chat_messages raised unexpectedly: %s", exc)
            chat_messages = [ChatMessage(role="user", content=user_message)]

        if not chat_messages:
            chat_messages = [ChatMessage(role="user", content=user_message)]

        approved_knowledge_context = self._build_approved_knowledge_context(
            user_message=user_message,
            max_hits=long_term_hits,
        )
        if approved_knowledge_context:
            if memory_context:
                memory_context = f"{memory_context}\n{approved_knowledge_context}"
            else:
                memory_context = approved_knowledge_context

        return chat_messages, memory_context, search_failed, retrieval_attempted

    def list_recent_messages(self, *, limit: int, offset: int = 0) -> list[dict]:
        return self.backend.list_recent_chat_messages(limit=limit, offset=offset)

    def record_exchange(
        self,
        user_message: str,
        assistant_response: str,
        assistant_session_id: str | None = None,
        reasoning_session_id: str | None = None,
        reasoning_state: dict | None = None,
    ) -> bool:
        return self.backend.record_exchange(
            user_message,
            assistant_response,
            assistant_session_id,
            reasoning_session_id=reasoning_session_id,
            reasoning_state=reasoning_state,
        )

    def _build_approved_knowledge_context(self, *, user_message: str, max_hits: int) -> str:
        safe_hits = max(1, int(max_hits))
        try:
            events = self.repository.list_recent(
                limit=max(safe_hits * 5, 20),
                status="active",
                namespace="knowledge",
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("failed to load approved knowledge events: %s", exc)
            return ""

        approved_events = [event for event in events if getattr(event, "review_status", "approved") == "approved"]
        if not approved_events:
            return ""

        ranked_events = _rank_approved_knowledge_events(
            events=approved_events,
            user_message=user_message,
            max_hits=safe_hits,
        )

        lines = ["【结构化知识（已审核）】"]
        for event in ranked_events:
            excerpt = _compact_text(event.content or "", limit=180)
            if not excerpt:
                continue
            source = _compact_text((event.source_ref or "knowledge/approved"), limit=120).replace(" ", "_")
            lines.append(f"- {source} {excerpt}")

        return "\n".join(lines) if len(lines) > 1 else ""


def _rank_approved_knowledge_events(
    *,
    events: list[MemoryEvent],
    user_message: str,
    max_hits: int,
) -> list[MemoryEvent]:
    safe_hits = max(1, int(max_hits))
    query_tokens = tokenize_text(user_message or "")
    normalized_query = (user_message or "").strip().lower()
    now_utc = datetime.now(timezone.utc)

    scored: list[tuple[float, float, float, float, MemoryEvent]] = []
    for event in events:
        relevance_score = _score_approved_knowledge_relevance(
            event=event,
            query_tokens=query_tokens,
            normalized_query=normalized_query,
        )
        freshness_score = _score_approved_knowledge_freshness(event=event, now_utc=now_utc)
        combined_score = _merge_approved_knowledge_scores(
            relevance_score=relevance_score,
            freshness_score=freshness_score,
            has_query=bool(query_tokens),
        )
        scored.append((combined_score, relevance_score, freshness_score, _event_timestamp(event), event))

    scored.sort(key=lambda item: (item[0], item[1], item[2], item[3]), reverse=True)
    return [item[4] for item in scored[:safe_hits]]


def _score_approved_knowledge_relevance(
    *,
    event: MemoryEvent,
    query_tokens: set[str],
    normalized_query: str,
) -> float:
    if not query_tokens:
        return 0.0

    event_index_text = " ".join(
        part
        for part in (
            event.content or "",
            " ".join(event.knowledge_tags),
            event.knowledge_type or "",
            event.source_ref or "",
        )
        if part
    )
    event_tokens = tokenize_text(event_index_text)
    overlap = len(query_tokens & event_tokens)
    token_coverage = overlap / max(1, len(query_tokens))
    phrase_bonus = 0.0
    if normalized_query and normalized_query in (event.content or "").lower():
        phrase_bonus = 0.25
    return min(1.0, token_coverage + phrase_bonus)


def _score_approved_knowledge_freshness(*, event: MemoryEvent, now_utc: datetime) -> float:
    created_at = event.created_at
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    age_seconds = max(0.0, (now_utc - created_at).total_seconds())
    freshness_half_life_seconds = 14 * 24 * 60 * 60
    return float(0.5 ** (age_seconds / freshness_half_life_seconds))


def _merge_approved_knowledge_scores(*, relevance_score: float, freshness_score: float, has_query: bool) -> float:
    if not has_query:
        return freshness_score
    return (relevance_score * 0.75) + (freshness_score * 0.25)


def _event_timestamp(event: MemoryEvent) -> float:
    created_at = event.created_at
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    return created_at.timestamp()


def _split_context_budget(context_limit: int) -> tuple[int, int]:
    total = max(1, int(context_limit))
    long_term_hits = max(1, int(round(total * LONG_TERM_CONTEXT_WEIGHT)))
    recent_turn_limit = max(1, int(round(total * RECENT_CONTEXT_WEIGHT)))
    return recent_turn_limit, long_term_hits


def _compact_text(text: str | None, *, limit: int) -> str:
    if not text:
        return ""
    compacted = " ".join(text.strip().split())
    if len(compacted) <= limit:
        return compacted
    return f"{compacted[: limit - 1].rstrip()}…"
