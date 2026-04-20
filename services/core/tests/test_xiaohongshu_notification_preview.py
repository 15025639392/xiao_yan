from app.api.platform_route_models import XiaohongshuNotificationPreviewRequest
from app.usecases.xiaohongshu_notification_preview import build_xiaohongshu_notification_preview_items
import pytest


def test_build_xiaohongshu_notification_preview_items_maps_entries_to_comment_requests():
    request = XiaohongshuNotificationPreviewRequest(
        message="请优先判断是否值得跟进成交",
        entries=[
            {
                "entry_id": "entry_1",
                "actor_name": "青栀",
                "actor_id": "user_1",
                "comment_text": "这个服务怎么合作？",
                "note_id": "note_1",
                "note_title": "副业获客",
                "note_text": "分享一个获客思路",
                "topic": "副业",
                "occurred_at": "2026-04-19T10:00:00Z",
            }
        ],
    )

    items = build_xiaohongshu_notification_preview_items(request)

    assert len(items) == 1
    assert items[0].item_type == "comment"
    assert items[0].message == "请优先判断是否值得跟进成交"
    assert items[0].comment is not None
    assert items[0].comment.author.name == "青栀"
    assert items[0].comment.comment_text == "这个服务怎么合作？"


def test_build_xiaohongshu_notification_preview_items_rejects_empty_entries():
    with pytest.raises(ValueError, match="xiaohongshu notification entries are required"):
        build_xiaohongshu_notification_preview_items(XiaohongshuNotificationPreviewRequest())
