from __future__ import annotations

from logging import getLogger
from typing import Protocol

from app.llm.schemas import ChatMessage
from app.memory.repository import MemoryRepository

logger = getLogger(__name__)

RECENT_CONTEXT_WEIGHT = 0.7
LONG_TERM_CONTEXT_WEIGHT = 0.3
HISTORICAL_MEMORY_CONTEXT_PREFIX = (
    "【历史经历与长期记忆】\n"
    "以下内容是过去积累下来的经历、内在状态或长期记忆线索，只用于连续性参考，"
    "不代表当前用户本地时间，也不应直接作为当前问候语或当前时间段判断依据。"
)


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
        request_key: str | None = None,
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

        if memory_context:
            memory_context = f"{HISTORICAL_MEMORY_CONTEXT_PREFIX}\n{memory_context}"

        return chat_messages, memory_context, search_failed, retrieval_attempted

    def list_recent_messages(self, *, limit: int, offset: int = 0) -> list[dict]:
        return self.backend.list_recent_chat_messages(limit=limit, offset=offset)

    def record_exchange(
        self,
        user_message: str,
        assistant_response: str,
        assistant_session_id: str | None = None,
        request_key: str | None = None,
        reasoning_session_id: str | None = None,
        reasoning_state: dict | None = None,
    ) -> bool:
        return self.backend.record_exchange(
            user_message,
            assistant_response,
            assistant_session_id,
            request_key=request_key,
            reasoning_session_id=reasoning_session_id,
            reasoning_state=reasoning_state,
        )

def _split_context_budget(context_limit: int) -> tuple[int, int]:
    # Keep a single user-facing budget for now, then split it into recent dialogue
    # continuity and long-term retrieval breadth.
    total = max(1, int(context_limit))
    long_term_hits = max(1, int(round(total * LONG_TERM_CONTEXT_WEIGHT)))
    recent_turn_limit = max(1, int(round(total * RECENT_CONTEXT_WEIGHT)))
    return recent_turn_limit, long_term_hits
