from fastapi.testclient import TestClient
import json

from app.api.deps import get_chat_gateway, get_chat_memory_runtime, get_persona_service, get_state_store
from app.api import xiaohongshu_handlers
from app.domain.models import BrowserSessionState, BrowserSessionStatus
from app.llm.schemas import ChatMessage
from app.main import app
from app.memory.chat_memory_runtime import ChatMemoryRuntime
from app.memory.repository import InMemoryMemoryRepository
from app.persona.service import InMemoryPersonaRepository, PersonaService
from app.runtime import StateStore
from app.usecases import xiaohongshu_creator_home_capture as creator_home_capture
from app.usecases import xiaohongshu_lead_capture as lead_capture
from app.usecases import xiaohongshu_publish_autofill as publish_autofill
from app.usecases import xiaohongshu_publish_via_mcp as publish_via_mcp
from app.usecases import xiaohongshu_text_image_autofill as text_image_autofill


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


def test_xiaohongshu_import_preview_endpoint_runs_comment_copilot_flow():
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
            "/platform-adapters/xiaohongshu/import-preview",
            json={
                "item_type": "comment",
                "comment": {
                    "comment_id": "comment_99",
                    "note_id": "note_99",
                    "comment_text": "这个适合刚开始做内容的人吗？",
                    "note_title": "把复杂事情收成一条主线",
                    "note_text": "先搭最小闭环。",
                    "author": {"id": "author_99", "name": "阿禾"},
                },
            },
        )

        assert response.status_code == 200
        body = response.json()
        assert body["platform_result"]["event"]["platform"] == "xiaohongshu"
        assert body["platform_result"]["event"]["event_type"] == "comment"
        assert body["platform_result"]["actions"][0]["action_type"] == "comment_reply_candidate"
        assert body["platform_result"]["delivery_results"][0]["status"] == "drafted"
        assert body["lead_assessment"]["is_lead"] is True
        assert body["lead_assessment"]["suggested_action"] == "reply_comment"
    finally:
        app.dependency_overrides.clear()


def test_xiaohongshu_import_preview_endpoint_rejects_missing_snapshot():
    client = TestClient(app)

    response = client.post(
        "/platform-adapters/xiaohongshu/import-preview",
        json={
            "item_type": "comment",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"]["message"] == "xiaohongshu comment snapshot is required"


def test_xiaohongshu_import_preview_file_endpoint_runs_batch_preview(tmp_path):
    payload_path = tmp_path / "xhs_batch.json"
    payload_path.write_text(
        json.dumps(
            {
                "items": [
                    {
                        "item_type": "comment",
                        "comment": {
                            "comment_id": "comment_201",
                            "note_id": "note_201",
                            "comment_text": "这个路径适合先试一版吗？",
                            "author": {"id": "author_201", "name": "阿禾"},
                        },
                    },
                    {
                        "item_type": "note",
                        "note": {
                            "note_id": "note_202",
                            "title": "先做最小闭环",
                            "note_text": "今天想讲怎么先把复杂度收窄。",
                            "author": {"id": "author_202", "name": "晚晴"},
                        },
                    },
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

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
            "/platform-adapters/xiaohongshu/import-preview-file",
            json={"path": str(payload_path)},
        )

        assert response.status_code == 200
        body = response.json()
        assert len(body) == 2
        assert body[0]["platform_result"]["actions"][0]["action_type"] == "comment_reply_candidate"
        assert body[1]["platform_result"]["actions"][0]["action_type"] == "note_draft_candidate"
        assert body[0]["lead_assessment"]["lead_stage"] in {"engage", "follow_up"}
        assert body[1]["lead_assessment"]["suggested_action"] == "prepare_note"
    finally:
        app.dependency_overrides.clear()


def test_xiaohongshu_notification_preview_endpoint_runs_real_session_like_comment_flow():
    app.dependency_overrides[get_chat_gateway] = lambda: _PlatformPreviewStubGateway()
    app.dependency_overrides[get_state_store] = lambda: StateStore()
    app.dependency_overrides[get_persona_service] = lambda: PersonaService(InMemoryPersonaRepository())
    app.dependency_overrides[get_chat_memory_runtime] = lambda: ChatMemoryRuntime(
        backend=_StubChatMemoryBackend(),
        repository=InMemoryMemoryRepository(),
    )
    client = TestClient(app)

    try:
        response = client.post(
            "/platform-adapters/xiaohongshu/notification-preview",
            json={
                "message": "请优先识别高意向成交线索",
                "entries": [
                    {
                        "entry_id": "entry_99",
                        "actor_name": "小叶",
                        "actor_id": "user_99",
                        "comment_text": "这个服务怎么购买？",
                        "note_id": "note_99",
                        "note_title": "AI获客实践",
                        "note_text": "分享一个获客转化思路",
                        "topic": "AI副业",
                        "occurred_at": "2026-04-19T10:00:00Z",
                    }
                ],
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["platform_result"]["event"]["event_type"] == "comment"
    assert body[0]["platform_result"]["user"]["display_name"] == "小叶"
    assert body[0]["lead_assessment"]["is_lead"] is True
    assert body[0]["lead_assessment"]["suggested_action"] == "follow_up_manually"


def test_xiaohongshu_notification_preview_endpoint_rejects_empty_entries():
    client = TestClient(app)

    response = client.post(
        "/platform-adapters/xiaohongshu/notification-preview",
        json={"entries": []},
    )

    assert response.status_code == 400
    assert response.json()["detail"]["message"] == "xiaohongshu notification entries are required"


def test_xiaohongshu_creator_home_preview_endpoint_builds_note_draft_candidates():
    app.dependency_overrides[get_chat_gateway] = lambda: _PlatformPreviewStubGateway()
    app.dependency_overrides[get_state_store] = lambda: StateStore()
    app.dependency_overrides[get_persona_service] = lambda: PersonaService(InMemoryPersonaRepository())
    app.dependency_overrides[get_chat_memory_runtime] = lambda: ChatMemoryRuntime(
        backend=_StubChatMemoryBackend(),
        repository=InMemoryMemoryRepository(),
    )
    client = TestClient(app)

    try:
        response = client.post(
            "/platform-adapters/xiaohongshu/creator-home-preview",
            json={
                "account_name": "小红薯66661C17",
                "topics": [
                    {
                        "topic": "#高颜值巧克力",
                        "participation_count": "30万人参与",
                        "view_count": "14.4亿次浏览",
                    }
                ],
                "activities": [
                    {
                        "title": "RED新生代创作大赛",
                        "date_range": "03-30 至 05-10",
                        "incentive_hint": "官方活动, 奖励多多",
                    }
                ],
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 2
    assert body[0]["platform_result"]["actions"][0]["action_type"] == "note_draft_candidate"
    assert body[0]["platform_result"]["event"]["event_type"] == "post"
    assert body[0]["lead_assessment"]["suggested_action"] == "prepare_note"
    assert body[0]["publish_draft"]["title"]
    assert len(body[0]["publish_draft"]["body_sections"]) >= 1
    assert len(body[0]["publish_draft"]["image_cards"]) == 3
    assert body[1]["platform_result"]["event"]["text"].startswith("这是小红薯66661C17在小红书创作首页看到的官方活动机会")


def test_xiaohongshu_creator_home_preview_endpoint_rejects_empty_snapshot():
    client = TestClient(app)

    response = client.post(
        "/platform-adapters/xiaohongshu/creator-home-preview",
        json={},
    )

    assert response.status_code == 400
    assert response.json()["detail"]["message"] == "xiaohongshu creator home topics or activities are required"


def test_xiaohongshu_creator_home_capture_endpoint_returns_current_chrome_snapshot(monkeypatch):
    monkeypatch.setattr(
        xiaohongshu_handlers,
        "capture_xiaohongshu_creator_home_via_browser_organ",
        lambda: creator_home_capture.XiaohongshuCreatorHomeCaptureResponse(
            source_url="https://creator.xiaohongshu.com/new/home",
            account_name="小红薯66661C17",
            raw_text="创作话题\n#高颜值巧克力",
            topics=[
                {
                    "topic": "#高颜值巧克力",
                    "participation_count": "30万人参与",
                    "view_count": "14.4亿次浏览",
                }
            ],
            activities=[
                {
                    "title": "RED新生代创作大赛",
                    "date_range": "03-30 至 05-10",
                    "incentive_hint": "官方活动, 奖励多多",
                }
            ],
        ),
    )

    client = TestClient(app)
    response = client.post("/platform-adapters/xiaohongshu/creator-home-capture")

    assert response.status_code == 200
    body = response.json()
    assert body["source_url"] == "https://creator.xiaohongshu.com/new/home"
    assert body["account_name"] == "小红薯66661C17"
    assert body["topics"][0]["topic"] == "#高颜值巧克力"


def test_xiaohongshu_publish_autofill_endpoint_returns_fill_status(monkeypatch):
    monkeypatch.setattr(
        xiaohongshu_handlers,
        "autofill_xiaohongshu_publish_page",
        lambda *, title, body, auto_publish=False, publish_selector="": publish_autofill.XiaohongshuPublishAutofillResponse(
            status="filled",
            publish_url="https://creator.xiaohongshu.com/publish/publish?from=xiao_yan&target=image",
            title=title,
            body=body,
            filled_title=True,
            filled_body=True,
            message="已打开发布页，并把标题和正文草稿填进当前图文发布表单。",
        ),
    )

    client = TestClient(app)
    response = client.post(
        "/platform-adapters/xiaohongshu/publish-autofill",
        json={
            "title": "测试标题",
            "body": "第一段\n第二段",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "filled"
    assert body["filled_title"] is True
    assert body["filled_body"] is True


def test_xiaohongshu_text_image_autofill_endpoint_returns_fill_status(monkeypatch):
    monkeypatch.setattr(
        xiaohongshu_handlers,
        "autofill_xiaohongshu_text_image_cards",
        lambda *, cards, trigger_generate: text_image_autofill.XiaohongshuTextImageAutofillResponse(
            status="submitted_generation",
            publish_url="https://creator.xiaohongshu.com/publish/publish?from=xiao_yan&target=image",
            cards=cards,
            filled_cards=len(cards),
            clicked_generate=trigger_generate,
            message="已把 3/3 张图卡文案填进文字配图，并触发了生成图片。",
        ),
    )

    client = TestClient(app)
    response = client.post(
        "/platform-adapters/xiaohongshu/text-image-autofill",
        json={
            "cards": ["封面图卡", "中间图卡", "结尾图卡"],
            "trigger_generate": True,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "submitted_generation"
    assert body["filled_cards"] == 3
    assert body["clicked_generate"] is True


def test_xiaohongshu_publish_via_mcp_endpoint_returns_publish_status(monkeypatch, tmp_path):
    cover = tmp_path / "cover.png"
    cover.write_bytes(b"cover")

    monkeypatch.setattr(
        xiaohongshu_handlers,
        "publish_xiaohongshu_image_post_via_mcp",
        lambda *, title, body, image_paths, client: publish_via_mcp.XiaohongshuPublishViaMcpResponse(
            status="submitted",
            message="MCP 发布结果：已提交图文发布",
            published_title=title,
            image_count=len(image_paths),
            image_paths=image_paths,
            post_url="https://www.xiaohongshu.com/explore/test",
            platform_post_id="note_123",
        ),
    )

    client = TestClient(app)
    response = client.post(
        "/platform-adapters/xiaohongshu/publish-via-mcp",
        json={
            "title": "测试标题",
            "body": "第一段\n第二段",
            "image_paths": [str(cover)],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "submitted"
    assert body["image_count"] == 1
    assert body["platform_post_id"] == "note_123"


def test_xiaohongshu_lead_capture_endpoint_returns_current_page_lead_summary(monkeypatch):
    monkeypatch.setattr(
        xiaohongshu_handlers,
        "capture_xiaohongshu_lead_signals_via_browser_organ",
        lambda *, session_id, title_hint: lead_capture.XiaohongshuLeadCaptureResponse(
            source_url="https://creator.xiaohongshu.com/new/home",
            note_title=title_hint or "测试标题",
            raw_text="点赞 128\n评论 12\n想加微信细聊预算和报价",
            like_count="128",
            collect_count="46",
            comment_count="12",
            share_count="3",
            direct_message_signal_count=1,
            wechat_signal_count=1,
            purchase_signal_count=1,
            lead_keywords=["微信", "报价"],
            matched_comment_lines=["想加微信细聊预算和报价"],
            tracking_template="内容标题：测试标题\n导到微信人数：1",
            message="已从当前小红书页面提取经营线索：评论 12，点赞 128，并命中 1 条值得跟进的评论线索。",
        ),
    )

    lead_state_store = StateStore()
    state = lead_state_store.get()
    state.browser_session = BrowserSessionState(
        session_id="active-browser-session",
        status=BrowserSessionStatus.ACTIVE,
    )
    lead_state_store.set(state)
    app.dependency_overrides[get_state_store] = lambda: lead_state_store

    client = TestClient(app)
    try:
        response = client.post(
            "/platform-adapters/xiaohongshu/lead-capture",
            json={"title_hint": "测试标题"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["note_title"] == "测试标题"
    assert body["comment_count"] == "12"
    assert body["wechat_signal_count"] == 1
    assert "导到微信人数：1" in body["tracking_template"]
