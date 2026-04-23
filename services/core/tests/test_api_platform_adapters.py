from fastapi.testclient import TestClient

from app.api.deps import get_chat_gateway, get_chat_memory_runtime, get_persona_service, get_state_store
from app.llm.schemas import ChatMessage
from app.main import app
from app.memory.chat_memory_runtime import ChatMemoryRuntime
from app.memory.repository import InMemoryMemoryRepository
from app.persona.service import InMemoryPersonaRepository, PersonaService
from app.runtime import StateStore


class _PlatformPreviewStubGateway:
    def create_response_with_tools(
        self,
        input_items,
        *,
        instructions=None,
        tools=None,
        previous_response_id=None,
    ):
        _ = (input_items, instructions, tools, previous_response_id)
        return {
            "id": "resp_platform_preview",
            "output": [
                {
                    "type": "message",
                    "role": "assistant",
                    "content": [
                        {
                            "type": "output_text",
                            "text": "可以先轻一点接住对方，再给一个低压力的下一步。",
                        }
                    ],
                }
            ],
            "output_text": "可以先轻一点接住对方，再给一个低压力的下一步。",
        }

    def close(self) -> None:
        return None


class _StubChatMemoryBackend:
    def search_context(
        self,
        query: str,
        *,
        exclude_current_room: bool = False,
        max_hits: int | None = None,
        retrieval_weight: float | None = None,
    ) -> str:
        _ = (query, exclude_current_room, max_hits, retrieval_weight)
        return ""

    def has_cross_room_long_term_sources(self, *, cache_seconds: int = 30) -> bool:
        _ = cache_seconds
        return False

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
        request_key: str | None = None,
        reasoning_session_id: str | None = None,
        reasoning_state: dict | None = None,
    ) -> bool:
        _ = (
            user_message,
            assistant_response,
            assistant_session_id,
            request_key,
            reasoning_session_id,
            reasoning_state,
        )
        return True


def test_list_platform_adapters_endpoint():
    client = TestClient(app)

    response = client.get("/platform-adapters")

    assert response.status_code == 200
    assert response.json() == {
        "platforms": [
            "wechat_manual",
            "wechat_official",
            "xiaohongshu",
        ]
    }


def test_platform_preview_endpoint_returns_canonicalized_preview():
    client = TestClient(app)

    response = client.post(
        "/platform-adapters/preview",
        json={
            "platform": "xiaohongshu",
            "raw_payload": {
                "note_id": "note_42",
                "comment_id": "comment_42",
                "comment_text": "这个适合副业起步吗？",
                "author": {"id": "author_42", "name": "青栀"},
            },
            "decision": {
                "kind": "comment_reply",
                "primary_text": "适合先从轻量版本开始，先跑通一条主线再扩。",
                "supporting_points": ["先选一个场景", "先验证反馈再扩写"],
            },
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["event"]["platform"] == "xiaohongshu"
    assert body["event"]["event_type"] == "comment"
    assert body["user"]["display_name"] == "青栀"
    assert body["actions"][0]["action_type"] == "comment_reply_candidate"
    assert body["delivery_results"][0]["status"] == "drafted"


def test_platform_preview_endpoint_rejects_unknown_platform():
    client = TestClient(app)

    response = client.post(
        "/platform-adapters/preview",
        json={
            "platform": "unknown_platform",
            "raw_payload": {},
            "decision": {
                "kind": "reply_suggestion",
                "primary_text": "hello",
            },
        },
    )

    assert response.status_code == 400
    assert response.json() == {
        "detail": {
            "message": "unsupported platform adapter: unknown_platform",
            "supported_platforms": [
                "wechat_manual",
                "wechat_official",
                "xiaohongshu",
            ],
        }
    }


def test_platform_preview_from_core_endpoint_accepts_internal_chat_output():
    client = TestClient(app)

    response = client.post(
        "/platform-adapters/preview-from-core",
        json={
            "platform": "wechat_manual",
            "raw_payload": {
                "conversation_id": "wx_conv_9",
                "scene": "manual_follow_up",
                "contact": {"id": "user_9", "name": "阿枫"},
                "message": {"id": "msg_9", "text": "那我们找时间细聊？"},
            },
            "internal_decision": {
                "source": "chat_submission",
                "output_text": "可以先接住对方意愿，再给出两个轻量时间选项。",
                "request_key": "request_9",
                "assistant_message_id": "assistant_9",
            },
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["event"]["platform"] == "wechat_manual"
    assert body["actions"][0]["action_type"] == "follow_up_suggestion"
    assert body["actions"][0]["metadata"]["decision_kind"] == "follow_up_suggestion"
    assert body["delivery_results"][0]["status"] == "drafted"


def test_platform_preview_from_core_endpoint_rejects_blank_internal_output():
    client = TestClient(app)

    response = client.post(
        "/platform-adapters/preview-from-core",
        json={
            "platform": "wechat_manual",
            "raw_payload": {
                "conversation_id": "wx_conv_10",
                "contact": {"id": "user_10"},
                "message": {"id": "msg_10", "text": "hi"},
            },
            "internal_decision": {
                "source": "assistant_text",
                "output_text": "   ",
            },
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"]["message"] == "internal decision output_text cannot be blank"


def test_platform_preview_from_draft_endpoint_accepts_stable_decision_dto():
    client = TestClient(app)

    response = client.post(
        "/platform-adapters/preview-from-draft",
        json={
            "platform": "xiaohongshu",
            "raw_payload": {
                "note_id": "note_66",
                "note_text": "今天想讲怎么收缩复杂度。",
                "author": {"id": "author_66", "name": "晚晴"},
            },
            "decision_draft": {
                "kind": "note_draft",
                "text": "标题：先把系统收成一条能跑的主线",
                "assistant_message_id": "assistant_66",
            },
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["actions"][0]["action_type"] == "note_draft_candidate"
    assert body["actions"][0]["metadata"]["decision_kind"] == "note_draft"


def test_platform_preview_from_chat_submission_endpoint_bridges_existing_chat_output():
    client = TestClient(app)

    response = client.post(
        "/platform-adapters/preview-from-chat-submission",
        json={
            "platform": "wechat_manual",
            "raw_payload": {
                "conversation_id": "wx_conv_20",
                "scene": "manual_follow_up",
                "contact": {"id": "user_20", "name": "阿沉"},
                "message": {"id": "msg_20", "text": "你觉得什么时候方便继续？"},
            },
            "submission": {
                "response_id": "resp_20",
                "assistant_message_id": "assistant_20",
                "request_key": "request_20",
                "reasoning_session_id": "reasoning_20",
            },
            "output_text": "可以先表示愿意继续，再给两个具体但轻量的时间选项。",
            "preferred_kind": "follow_up_suggestion",
            "supporting_points": ["先接住意愿", "再给时间窗口"],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["actions"][0]["action_type"] == "follow_up_suggestion"
    assert body["actions"][0]["metadata"]["decision_kind"] == "follow_up_suggestion"
    assert body["delivery_results"][0]["status"] == "drafted"


def test_platform_preview_from_chat_submission_endpoint_rejects_blank_output():
    client = TestClient(app)

    response = client.post(
        "/platform-adapters/preview-from-chat-submission",
        json={
            "platform": "wechat_manual",
            "raw_payload": {
                "conversation_id": "wx_conv_21",
                "contact": {"id": "user_21"},
                "message": {"id": "msg_21", "text": "hi"},
            },
            "submission": {
                "assistant_message_id": "assistant_21",
            },
            "output_text": "   ",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"]["message"] == "chat submission output_text cannot be blank"


def test_platform_preview_with_chat_endpoint_runs_chat_then_returns_platform_preview():
    def override_chat_gateway():
        return _PlatformPreviewStubGateway()

    def override_chat_memory_runtime():
        return ChatMemoryRuntime(
            backend=_StubChatMemoryBackend(),
            repository=InMemoryMemoryRepository(),
        )

    def override_state_store():
        return StateStore()

    def override_persona_service():
        return PersonaService(repository=InMemoryPersonaRepository())

    app.dependency_overrides[get_chat_gateway] = override_chat_gateway
    app.dependency_overrides[get_chat_memory_runtime] = override_chat_memory_runtime
    app.dependency_overrides[get_state_store] = override_state_store
    app.dependency_overrides[get_persona_service] = override_persona_service

    try:
        client = TestClient(app)
        response = client.post(
            "/platform-adapters/preview-with-chat",
            json={
                "platform": "wechat_manual",
                "raw_payload": {
                    "conversation_id": "wx_conv_30",
                    "scene": "manual_follow_up",
                    "contact": {"id": "user_30", "name": "阿临"},
                    "message": {"id": "msg_30", "text": "那我们什么时候继续？"},
                },
                "preferred_kind": "follow_up_suggestion",
            },
        )

        assert response.status_code == 200
        body = response.json()
        assert body["submission"]["response_id"] == "resp_platform_preview"
        assert body["output_text"] == "可以先轻一点接住对方，再给一个低压力的下一步。"
        assert body["platform_result"]["actions"][0]["action_type"] == "follow_up_suggestion"
        assert body["platform_result"]["delivery_results"][0]["status"] == "drafted"
    finally:
        app.dependency_overrides.clear()
