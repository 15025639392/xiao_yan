from app.platform_adapters.adapters import XiaohongshuAdapter
from app.usecases.xiaohongshu_lead_assessment import assess_xiaohongshu_lead


def test_assess_xiaohongshu_comment_as_engage_lead():
    event = XiaohongshuAdapter().parse_event(
        {
            "comment_id": "comment_301",
            "note_id": "note_301",
            "comment_text": "这个适合新手吗？怎么做比较稳？",
            "author": {"id": "author_301", "name": "青栀"},
        }
    )

    result = assess_xiaohongshu_lead(event)

    assert result.is_lead is True
    assert result.intent_level == "medium"
    assert result.lead_stage == "engage"
    assert result.suggested_action == "reply_comment"


def test_assess_xiaohongshu_comment_as_high_intent_follow_up():
    event = XiaohongshuAdapter().parse_event(
        {
            "comment_id": "comment_302",
            "note_id": "note_302",
            "comment_text": "这个服务多少钱，怎么购买？",
            "author": {"id": "author_302", "name": "晚晴"},
        }
    )

    result = assess_xiaohongshu_lead(event)

    assert result.is_lead is True
    assert result.intent_level == "high"
    assert result.lead_stage == "follow_up"
    assert result.suggested_action == "follow_up_manually"


def test_assess_xiaohongshu_note_as_observe_content_opportunity():
    event = XiaohongshuAdapter().parse_event(
        {
            "note_id": "note_303",
            "note_text": "今天想讲怎么把复杂事情收成一条主线。",
            "author": {"id": "author_303", "name": "阿禾"},
        }
    )

    result = assess_xiaohongshu_lead(event)

    assert result.is_lead is False
    assert result.lead_stage == "observe"
    assert result.suggested_action == "prepare_note"
