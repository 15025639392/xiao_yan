import pytest

from app.platform_adapters.models import CoreDecision
from app.platform_adapters.registry import build_platform_adapter_registry
from app.platform_adapters.service import PlatformAdapterService


def test_platform_adapter_registry_lists_supported_platforms():
    registry = build_platform_adapter_registry()

    assert registry.list_platforms() == [
        "wechat_manual",
        "wechat_official",
        "xiaohongshu",
    ]


def test_platform_adapter_service_dispatches_to_requested_platform():
    service = PlatformAdapterService(registry=build_platform_adapter_registry())

    result = service.process(
        platform="wechat_manual",
        raw_payload={
            "conversation_id": "wx_conv_2",
            "contact": {"id": "user_2", "name": "阿禾"},
            "message": {"id": "msg_2", "text": "这周怎么安排比较合适？"},
        },
        decision=CoreDecision(
            kind="follow_up_suggestion",
            primary_text="先给对方两个可选时间，再观察回应。",
        ),
    )

    assert result.event.platform == "wechat_manual"
    assert result.user.display_name == "阿禾"
    assert result.actions[0].action_type == "follow_up_suggestion"
    assert result.delivery_results[0].status == "drafted"


def test_platform_adapter_service_rejects_unknown_platform():
    service = PlatformAdapterService(registry=build_platform_adapter_registry())

    with pytest.raises(ValueError, match="unsupported platform adapter"):
        service.process(
            platform="unknown_platform",
            raw_payload={},
            decision=CoreDecision(kind="reply_suggestion", primary_text="hello"),
        )


def test_platform_adapter_service_can_map_internal_chat_output_before_rendering():
    service = PlatformAdapterService(registry=build_platform_adapter_registry())

    result = service.process_internal_decision(
        platform="xiaohongshu",
        raw_payload={
            "note_id": "note_11",
            "comment_id": "comment_11",
            "comment_text": "适合刚开始做内容的人吗？",
            "author": {"id": "author_11", "name": "白露"},
        },
        decision_input={
            "source": "chat_submission",
            "output_text": "适合先从最小版本开始，先稳定更新，再慢慢扩结构。",
            "request_key": "request_11",
        },
    )

    assert result.actions[0].action_type == "comment_reply_candidate"
    assert result.actions[0].metadata["decision_kind"] == "comment_reply"
    assert result.delivery_results[0].status == "drafted"


def test_platform_adapter_service_can_process_stable_decision_draft():
    service = PlatformAdapterService(registry=build_platform_adapter_registry())

    result = service.process_decision_draft(
        platform="wechat_manual",
        raw_payload={
            "conversation_id": "wx_conv_12",
            "contact": {"id": "user_12", "name": "阿青"},
            "message": {"id": "msg_12", "text": "这周找时间聊聊？"},
        },
        decision_draft={
            "kind": "reply_suggestion",
            "text": "可以先回应愿意聊，再给一个不压迫的时间窗口。",
            "assistant_message_id": "assistant_12",
        },
    )

    assert result.actions[0].action_type == "reply_suggestion"
    assert result.actions[0].metadata["decision_kind"] == "reply_suggestion"
    assert result.delivery_results[0].status == "drafted"
