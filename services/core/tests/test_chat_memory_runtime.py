from __future__ import annotations

from app.llm.schemas import ChatMessage
from app.memory.chat_memory_runtime import ChatMemoryRuntime
from app.memory.models import MemoryEvent
from app.memory.repository import InMemoryMemoryRepository


class _StubChatMemoryBackend:
    def __init__(
        self,
        *,
        search_context_text: str = "",
        has_cross_room_long_term_sources_value: bool = True,
        raise_on_build: bool = False,
    ) -> None:
        self.search_context_text = search_context_text
        self.has_cross_room_long_term_sources_value = has_cross_room_long_term_sources_value
        self.raise_on_build = raise_on_build
        self.search_calls: list[dict] = []
        self.build_limits: list[int] = []
        self.record_calls: list[tuple[str, str, str | None]] = []
        self.recent_messages: list[dict] = [
            {"id": "assistant_1", "role": "assistant", "content": "上一句", "created_at": None},
            {"id": "user_1", "role": "user", "content": "上一轮", "created_at": None},
        ]

    def search_context(
        self,
        query: str,
        *,
        exclude_current_room: bool = False,
        max_hits: int | None = None,
        retrieval_weight: float | None = None,
    ) -> str:
        self.search_calls.append(
            {
                "query": query,
                "exclude_current_room": exclude_current_room,
                "max_hits": max_hits,
                "retrieval_weight": retrieval_weight,
            }
        )
        return self.search_context_text

    def has_cross_room_long_term_sources(self, *, cache_seconds: int = 30) -> bool:
        _ = cache_seconds
        return self.has_cross_room_long_term_sources_value

    def build_chat_messages(self, user_message: str, *, limit: int) -> list[ChatMessage]:
        self.build_limits.append(limit)
        if self.raise_on_build:
            raise RuntimeError("build failed")
        return [ChatMessage(role="assistant", content="上一句"), ChatMessage(role="user", content=user_message)]

    def list_recent_chat_messages(self, *, limit: int, offset: int = 0) -> list[dict]:
        _ = (limit, offset)
        return list(self.recent_messages)

    def record_exchange(
        self,
        user_message: str,
        assistant_response: str,
        assistant_session_id: str | None = None,
        reasoning_session_id: str | None = None,
        reasoning_state: dict | None = None,
    ) -> bool:
        _ = (reasoning_session_id, reasoning_state)
        self.record_calls.append((user_message, assistant_response, assistant_session_id))
        return True


def test_chat_memory_runtime_resolve_context_combines_long_term_and_approved_knowledge():
    repository = InMemoryMemoryRepository()
    repository.save_event(
        MemoryEvent(
            kind="fact",
            content="用户偏好在夜里聊星星。",
            namespace="knowledge",
            source_ref="knowledge/night-sky",
            review_status="approved",
        )
    )
    backend = _StubChatMemoryBackend(search_context_text="【长期记忆检索】\n- wing/preferences (相似度 0.91) 记得你喜欢夜空")
    runtime = ChatMemoryRuntime(backend=backend, repository=repository)

    messages, memory_context, search_failed, retrieval_attempted = runtime.resolve_context(
        user_message="还记得星星吗",
        context_limit=10,
    )

    assert [message.content for message in messages] == ["上一句", "还记得星星吗"]
    assert "【长期记忆检索】" in memory_context
    assert "【结构化知识（已审核）】" in memory_context
    assert "knowledge/night-sky" in memory_context
    assert search_failed is False
    assert retrieval_attempted is True
    assert backend.search_calls == [
        {
            "query": "还记得星星吗",
            "exclude_current_room": True,
            "max_hits": 3,
            "retrieval_weight": 0.3,
        }
    ]
    assert backend.build_limits == [7]


def test_chat_memory_runtime_skips_long_term_search_when_no_cross_room_sources():
    repository = InMemoryMemoryRepository()
    repository.save_event(
        MemoryEvent(
            kind="fact",
            content="这条知识仍然应该出现在已审核知识里。",
            namespace="knowledge",
            review_status="approved",
        )
    )
    backend = _StubChatMemoryBackend(has_cross_room_long_term_sources_value=False)
    runtime = ChatMemoryRuntime(backend=backend, repository=repository)

    _, memory_context, search_failed, retrieval_attempted = runtime.resolve_context(
        user_message="今天聊什么",
        context_limit=10,
    )

    assert "【结构化知识（已审核）】" in memory_context
    assert backend.search_calls == []
    assert search_failed is False
    assert retrieval_attempted is False


def test_chat_memory_runtime_falls_back_to_current_user_message_when_history_build_fails():
    runtime = ChatMemoryRuntime(
        backend=_StubChatMemoryBackend(raise_on_build=True),
        repository=InMemoryMemoryRepository(),
    )

    messages, memory_context, search_failed, retrieval_attempted = runtime.resolve_context(
        user_message="hello",
        context_limit=5,
    )

    assert len(messages) == 1
    assert messages[0].role == "user"
    assert messages[0].content == "hello"
    assert memory_context == ""
    assert search_failed is False
    assert retrieval_attempted is True
