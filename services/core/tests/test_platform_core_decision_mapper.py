import pytest

from app.platform_adapters.adapters import WechatManualAdapter, XiaohongshuAdapter
from app.platform_adapters.core_decision_mapper import CoreDecisionMapper
from app.platform_adapters.models import CoreDecisionDraft, InternalDecisionInput


def test_core_decision_mapper_uses_wechat_manual_scene_to_pick_follow_up_kind():
    adapter = WechatManualAdapter()
    event = adapter.parse_event(
        {
            "conversation_id": "wx_conv_3",
            "scene": "manual_follow_up",
            "contact": {"id": "user_3", "name": "阿宁"},
            "message": {"id": "msg_3", "text": "那我们下周再约？"},
        }
    )

    decision = CoreDecisionMapper().map_from_internal(
        platform="wechat_manual",
        event=event,
        decision_input=InternalDecisionInput(
            source="chat_submission",
            output_text="可以先确认对方下周哪天方便，再给两个轻量选项。",
            request_key="req_3",
            assistant_message_id="assistant_3",
        ),
    )

    assert decision.kind == "follow_up_suggestion"
    assert decision.primary_text == "可以先确认对方下周哪天方便，再给两个轻量选项。"
    assert decision.metadata["source"] == "chat_submission"
    assert decision.metadata["request_key"] == "req_3"


def test_core_decision_mapper_uses_xiaohongshu_comment_as_comment_reply():
    adapter = XiaohongshuAdapter()
    event = adapter.parse_event(
        {
            "note_id": "note_5",
            "comment_id": "comment_5",
            "comment_text": "学生党能直接照着做吗？",
            "author": {"id": "author_5", "name": "松果"},
        }
    )

    decision = CoreDecisionMapper().map_from_internal(
        platform="xiaohongshu",
        event=event,
        decision_input=InternalDecisionInput(
            output_text="可以先从最轻的一版开始，别一上来把链路铺太满。",
            supporting_points=["先选一个场景验证", "先看反馈再加复杂度"],
        ),
    )

    assert decision.kind == "comment_reply"
    assert decision.supporting_points == ["先选一个场景验证", "先看反馈再加复杂度"]


def test_core_decision_mapper_rejects_blank_output_text():
    adapter = WechatManualAdapter()
    event = adapter.parse_event(
        {
            "conversation_id": "wx_conv_4",
            "contact": {"id": "user_4"},
            "message": {"id": "msg_4", "text": "hi"},
        }
    )

    with pytest.raises(ValueError, match="output_text cannot be blank"):
        CoreDecisionMapper().map_from_internal(
            platform="wechat_manual",
            event=event,
            decision_input=InternalDecisionInput(output_text="  "),
        )


def test_core_decision_mapper_maps_stable_decision_draft():
    decision = CoreDecisionMapper().map_from_draft(
        decision_draft=CoreDecisionDraft(
            kind="note_draft",
            text="标题先稳住，再把正文控制在一条主线上。",
            request_key="request_7",
            assistant_message_id="assistant_7",
        )
    )

    assert decision.kind == "note_draft"
    assert decision.primary_text == "标题先稳住，再把正文控制在一条主线上。"
    assert decision.metadata["source"] == "core_decision_draft"
    assert decision.metadata["request_key"] == "request_7"
