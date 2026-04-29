from __future__ import annotations

from fastapi.testclient import TestClient

from app.api.deps import get_chat_gateway, get_mempalace_adapter, get_memory_repository, get_state_store
from app.chat.ai_collaboration_coach import (
    append_ai_collaboration_coach_context,
    classify_ai_collaboration_stage,
    should_enable_ai_collaboration_coach,
)
from app.llm.schemas import ChatMessage
from app.memory.repository import InMemoryMemoryRepository
from app.runtime import StateStore
from app.main import app


class StubGateway:
    def __init__(self) -> None:
        self.last_messages: list[ChatMessage] = []
        self.last_instructions: str | None = None

    def stream_response(self, messages, instructions=None):
        self.last_messages = list(messages)
        self.last_instructions = instructions
        yield {"type": "response_started", "response_id": "resp_ai_coach"}
        yield {"type": "text_delta", "delta": "我先帮你整理这次 AI 协作。"}
        yield {
            "type": "response_completed",
            "response_id": "resp_ai_coach",
            "output_text": "我先帮你整理这次 AI 协作。",
        }

    def close(self) -> None:
        return None


class StubMemPalaceAdapter:
    def __init__(self) -> None:
        self.record_calls: list[tuple[str, str, str | None]] = []

    def has_cross_room_long_term_sources(self, *, cache_seconds: int = 30) -> bool:
        _ = cache_seconds
        return False

    def search_context(self, query: str, **kwargs) -> str:
        _ = (query, kwargs)
        return ""

    def build_chat_messages(self, user_message: str, *, limit: int) -> list[ChatMessage]:
        _ = limit
        return [ChatMessage(role="user", content=user_message)]

    def list_recent_chat_messages(self, *, limit: int, offset: int = 0) -> list[dict]:
        _ = (limit, offset)
        return []

    def record_exchange(
        self,
        user_message: str,
        assistant_response: str,
        assistant_session_id: str | None = None,
        **kwargs,
    ) -> bool:
        _ = kwargs
        self.record_calls.append((user_message, assistant_response, assistant_session_id))
        return True


def test_ai_collaboration_coach_detects_supported_entry_points():
    assert should_enable_ai_collaboration_coach("帮我整理给 AI 的请求")
    assert should_enable_ai_collaboration_coach("Codex 改完了，帮我看看")
    assert should_enable_ai_collaboration_coach("帮我把这个想法交给 ChatGPT")
    assert should_enable_ai_collaboration_coach("Claude 的回复帮我评估一下")
    assert should_enable_ai_collaboration_coach("Cursor 改完了，帮我审阅")
    assert should_enable_ai_collaboration_coach("帮我生成下一轮追问")
    assert should_enable_ai_collaboration_coach("帮我用 AI 推进这个事")


def test_ai_collaboration_coach_ignores_generic_chat():
    assert not should_enable_ai_collaboration_coach("今天聊点轻松的")


def test_ai_collaboration_coach_classifies_stage():
    assert classify_ai_collaboration_stage("帮我整理给 AI 的请求") == "context_packaging"
    assert classify_ai_collaboration_stage("帮我把这个想法交给 ChatGPT") == "context_packaging"
    assert classify_ai_collaboration_stage("Codex 改完了，帮我看看") == "result_review"
    assert classify_ai_collaboration_stage("DeepSeek 的输出帮我检查一下") == "result_review"
    assert classify_ai_collaboration_stage("帮我生成下一轮追问") == "next_prompt"
    assert classify_ai_collaboration_stage("帮我用 AI 推进这个事") == "general"
    assert classify_ai_collaboration_stage("今天聊点轻松的") is None


def test_ai_collaboration_coach_appends_boundary_guidance():
    instructions = append_ai_collaboration_coach_context(
        "base",
        user_message="帮我检查 AI 的回答",
    )

    assert "[AI 协作辅导]" in instructions
    assert "[澄清框架]" in instructions
    assert "本轮澄清层次：task、intent、tradeoff、consistency、collaboration_method" in instructions
    assert "当前证据足不足以支持完成度判断？" in instructions
    assert "保留用户的最终判断权" in instructions
    assert "[当前协作阶段]" in instructions
    assert "[本阶段输出结构]" in instructions
    assert "不默认自动调用外部 AI" in instructions
    assert "不要只补任务字段" in instructions
    assert "意图：用户为什么现在想做这件事" in instructions
    assert "一致性：当前需求是否偏离用户长期偏好" in instructions
    assert "协作偏好候选" in instructions
    assert "不要宣称已经写入长期记忆" in instructions
    assert "任务上下文边界" in instructions
    assert "不要把不同项目、不同需求或不同外部 AI 会话的证据混在一起判断" in instructions
    assert "必要时建议另起一个任务上下文" in instructions
    assert "证据缺口" in instructions
    assert "当前更像“检查 AI 的回答”" in instructions
    assert "完成度判断" in instructions
    assert "待确认的协作偏好候选" in instructions
    assert "不要把它写成普通代码审查" in instructions
    assert "证据不足时的回应" in instructions
    assert "我现在只能基于你给出的材料做有限判断" in instructions
    assert "原始需求、交给外部 AI 的提示词、外部 AI 输出" in instructions
    assert "协作证据包" in instructions
    assert "关键证据（测试、来源、diff、截图或验证结果）" in instructions
    assert "用户最不放心的地方" in instructions


def test_ai_collaboration_coach_adds_prompt_contract_for_next_prompt_stage():
    instructions = append_ai_collaboration_coach_context(
        "base",
        user_message="帮我生成下一轮追问",
    )

    assert "当前更像“生成下一轮追问”" in instructions
    assert "可复制的下一轮提示词" in instructions
    assert "验证方式" in instructions


def test_ai_collaboration_coach_adds_general_stage_guidance():
    instructions = append_ai_collaboration_coach_context(
        "base",
        user_message="帮我用 AI 推进这个事",
    )

    assert "当前属于一般 AI 协作辅导" in instructions
    assert "先说明你判断用户卡在哪个协作环节" in instructions
    assert "一次只问能解锁下一步的一个问题" in instructions


def test_post_chat_injects_ai_collaboration_coach_context():
    memory_repository = InMemoryMemoryRepository()
    state_store = StateStore(memory_repository=memory_repository)
    gateway = StubGateway()
    mempalace_adapter = StubMemPalaceAdapter()

    def override_gateway():
        try:
            yield gateway
        finally:
            gateway.close()

    def override_memory_repository():
        return memory_repository

    def override_state_store():
        return state_store

    def override_mempalace_adapter():
        return mempalace_adapter

    app.dependency_overrides[get_chat_gateway] = override_gateway
    app.dependency_overrides[get_memory_repository] = override_memory_repository
    app.dependency_overrides[get_state_store] = override_state_store
    app.dependency_overrides[get_mempalace_adapter] = override_mempalace_adapter

    client = TestClient(app)
    response = client.post("/chat", json={"message": "Codex 改完了，帮我看看"})

    assert response.status_code == 200
    assert gateway.last_instructions is not None
    assert "[AI 协作辅导]" in gateway.last_instructions
    assert "不默认自动调用外部 AI" in gateway.last_instructions
    assert "原始需求" in gateway.last_instructions


def test_post_resume_chat_injects_ai_collaboration_coach_context():
    memory_repository = InMemoryMemoryRepository()
    state_store = StateStore(memory_repository=memory_repository)
    gateway = StubGateway()
    mempalace_adapter = StubMemPalaceAdapter()

    def override_gateway():
        try:
            yield gateway
        finally:
            gateway.close()

    def override_memory_repository():
        return memory_repository

    def override_state_store():
        return state_store

    def override_mempalace_adapter():
        return mempalace_adapter

    app.dependency_overrides[get_chat_gateway] = override_gateway
    app.dependency_overrides[get_memory_repository] = override_memory_repository
    app.dependency_overrides[get_state_store] = override_state_store
    app.dependency_overrides[get_mempalace_adapter] = override_mempalace_adapter

    client = TestClient(app)
    response = client.post(
        "/chat/resume",
        json={
            "message": "Claude 的回复帮我评估一下",
            "assistant_message_id": "assistant_ai_coach_resume",
            "partial_content": "前半段",
        },
    )

    assert response.status_code == 200
    assert gateway.last_instructions is not None
    assert "[AI 协作辅导]" in gateway.last_instructions
    assert "当前更像“检查 AI 的回答”" in gateway.last_instructions
