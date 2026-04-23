import pytest

from app.api.platform_route_models import XiaohongshuCreatorHomePreviewRequest
from app.usecases.xiaohongshu_creator_home_preview import build_xiaohongshu_creator_home_preview_items


def test_build_xiaohongshu_creator_home_preview_items_maps_topics_and_activities():
    request = XiaohongshuCreatorHomePreviewRequest(
        account_name="小红薯66661C17",
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
    )

    items = build_xiaohongshu_creator_home_preview_items(request)

    assert len(items) == 2
    assert items[0].source_kind == "topic"
    assert items[0].request.item_type == "note"
    assert items[0].request.note is not None
    assert "#高颜值巧克力" in items[0].request.note.note_text
    assert "数字生命账号经营的轻科普笔记草稿" in items[0].request.note.note_text
    assert items[1].source_kind == "activity"
    assert "RED新生代创作大赛" in items[1].request.note.note_text
    assert "轻科普或观察型笔记草稿" in items[1].request.note.note_text


def test_build_xiaohongshu_creator_home_preview_items_rejects_empty_opportunities():
    with pytest.raises(ValueError, match="xiaohongshu creator home topics or activities are required"):
        build_xiaohongshu_creator_home_preview_items(XiaohongshuCreatorHomePreviewRequest())
