from app.platform_adapters.adapters import (
    WechatManualAdapter,
    WechatOfficialAdapter,
    XiaohongshuAdapter,
)
from app.platform_adapters.models import CoreDecision


def test_wechat_manual_adapter_parses_payload_into_canonical_event():
    adapter = WechatManualAdapter()

    event = adapter.parse_event(
        {
            "conversation_id": "wx_conv_1",
            "scene": "manual_follow_up",
            "contact": {
                "id": "user_1",
                "name": "小林",
                "remark": "正在考虑合作",
            },
            "message": {
                "id": "msg_1",
                "sender_id": "user_1",
                "text": "你明天下午有空吗？",
                "sent_at": "2026-04-19T10:00:00+08:00",
            },
        }
    )

    assert event.platform == "wechat_manual"
    assert event.thread_id == "wx_conv_1"
    assert event.text == "你明天下午有空吗？"
    assert event.user.user_id == "user_1"
    assert event.user.display_name == "小林"
    assert event.metadata["scene"] == "manual_follow_up"


def test_wechat_manual_adapter_renders_reply_suggestion_action():
    adapter = WechatManualAdapter()
    event = adapter.parse_event(
        {
            "conversation_id": "wx_conv_1",
            "contact": {"id": "user_1", "name": "小林"},
            "message": {"id": "msg_1", "text": "最近怎么样"},
        }
    )
    decision = CoreDecision(
        kind="reply_suggestion",
        primary_text="可以先轻一点回应，再顺手确认对方具体时间。",
        supporting_points=["先回应近况", "再确认时间窗口"],
    )

    actions = adapter.render_actions(event, event.user, decision)

    assert len(actions) == 1
    assert actions[0].action_type == "reply_suggestion"
    assert "先回应近况" in actions[0].content


def test_xiaohongshu_adapter_parses_comment_payload():
    adapter = XiaohongshuAdapter()

    event = adapter.parse_event(
        {
            "comment_id": "comment_1",
            "note_id": "note_9",
            "comment_text": "这个方案适合新手吗？",
            "topic": "效率工具",
            "author": {
                "id": "author_1",
                "name": "阿青",
            },
        }
    )

    assert event.platform == "xiaohongshu"
    assert event.event_type == "comment"
    assert event.thread_id == "note_9"
    assert event.text == "这个方案适合新手吗？"
    assert event.user.display_name == "阿青"


def test_xiaohongshu_adapter_renders_note_draft_candidate():
    adapter = XiaohongshuAdapter()
    event = adapter.parse_event(
        {
            "note_id": "note_9",
            "note_text": "今天想整理一个轻量执行系统。",
            "author": {"id": "author_1", "name": "阿青"},
        }
    )
    decision = CoreDecision(
        kind="note_draft",
        primary_text="标题：把复杂系统收成一条能跑的主线",
    )

    actions = adapter.render_actions(event, event.user, decision)

    assert [action.action_type for action in actions] == ["note_draft_candidate"]
    assert actions[0].title == "小红书笔记草稿"


def test_wechat_official_adapter_deliver_returns_simulated_draft_result():
    adapter = WechatOfficialAdapter()
    event = adapter.parse_event(
        {
            "conversation_id": "official_1",
            "openid": "openid_1",
            "text": "你好",
        }
    )
    decision = CoreDecision(kind="reply_suggestion", primary_text="你好呀，这里先给你一个回复草稿。")

    results = adapter.deliver(adapter.render_actions(event, event.user, decision))

    assert len(results) == 1
    assert results[0].platform == "wechat_official"
    assert results[0].status == "drafted"
