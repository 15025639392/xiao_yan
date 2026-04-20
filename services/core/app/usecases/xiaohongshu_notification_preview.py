from __future__ import annotations

from app.api.platform_route_models import (
    XiaohongshuAuthorSnapshot,
    XiaohongshuCommentSnapshot,
    XiaohongshuImportPreviewRequest,
    XiaohongshuNotificationPreviewRequest,
)


def build_xiaohongshu_notification_preview_items(
    request: XiaohongshuNotificationPreviewRequest,
) -> list[XiaohongshuImportPreviewRequest]:
    if not request.entries:
        raise ValueError("xiaohongshu notification entries are required")
    return [
        XiaohongshuImportPreviewRequest(
            item_type="comment",
            message=request.message,
            comment=XiaohongshuCommentSnapshot(
                comment_id=entry.entry_id,
                note_id=entry.note_id,
                comment_text=entry.comment_text,
                commented_at=entry.occurred_at,
                source_url=entry.source_url,
                note_title=entry.note_title,
                note_text=entry.note_text,
                topic=entry.topic,
                author=XiaohongshuAuthorSnapshot(
                    id=entry.actor_id or entry.entry_id,
                    name=entry.actor_name,
                    bio=entry.actor_bio,
                ),
            ),
        )
        for entry in request.entries
    ]
