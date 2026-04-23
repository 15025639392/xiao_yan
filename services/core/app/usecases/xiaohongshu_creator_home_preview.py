from __future__ import annotations

from pydantic import BaseModel

from app.api.platform_route_models import (
    XiaohongshuAuthorSnapshot,
    XiaohongshuCreatorHomePreviewRequest,
    XiaohongshuImportPreviewRequest,
    XiaohongshuNoteSnapshot,
)
from app.usecases.xiaohongshu_content_strategy import build_xiaohongshu_creator_home_note_text


class XiaohongshuCreatorOpportunityItem(BaseModel):
    source_kind: str
    title: str
    summary: str
    request: XiaohongshuImportPreviewRequest


def build_xiaohongshu_creator_home_preview_items(
    request: XiaohongshuCreatorHomePreviewRequest,
) -> list[XiaohongshuCreatorOpportunityItem]:
    items: list[XiaohongshuCreatorOpportunityItem] = []
    account_name = (request.account_name or "当前账号").strip() or "当前账号"

    for topic in request.topics:
        title = _normalize_title(topic.topic, fallback="创作话题")
        summary = " ".join(
            part
            for part in [
                f"参与人数：{topic.participation_count}" if topic.participation_count else "",
                f"浏览量：{topic.view_count}" if topic.view_count else "",
            ]
            if part
        ).strip()
        note_text = build_xiaohongshu_creator_home_note_text(
            source_kind="topic",
            account_name=account_name,
            title=title,
            summary=summary,
        )
        items.append(
            XiaohongshuCreatorOpportunityItem(
                source_kind="topic",
                title=title,
                summary=summary,
                request=_build_note_request(
                    note_id=f"creator_topic:{title}",
                    title=title,
                    note_text=note_text,
                    topic=title,
                    message=request.message,
                ),
            )
        )

    for activity in request.activities:
        title = _normalize_title(activity.title, fallback="热门活动")
        summary = " ".join(
            part
            for part in [
                f"活动时间：{activity.date_range}" if activity.date_range else "",
                f"激励提示：{activity.incentive_hint}" if activity.incentive_hint else "",
            ]
            if part
        ).strip()
        note_text = build_xiaohongshu_creator_home_note_text(
            source_kind="activity",
            account_name=account_name,
            title=title,
            summary=summary,
        )
        items.append(
            XiaohongshuCreatorOpportunityItem(
                source_kind="activity",
                title=title,
                summary=summary,
                request=_build_note_request(
                    note_id=f"creator_activity:{title}",
                    title=title,
                    note_text=note_text,
                    topic="活动机会",
                    message=request.message,
                ),
            )
        )

    if not items:
        raise ValueError("xiaohongshu creator home topics or activities are required")
    return items


def _build_note_request(
    *,
    note_id: str,
    title: str,
    note_text: str,
    topic: str | None,
    message: str | None,
) -> XiaohongshuImportPreviewRequest:
    return XiaohongshuImportPreviewRequest(
        item_type="note",
        message=message,
        note=XiaohongshuNoteSnapshot(
            note_id=note_id,
            title=title,
            note_text=note_text,
            topic=topic,
            source_scene="creator_home",
            author=XiaohongshuAuthorSnapshot(id="creator_home", name="creator_home"),
        ),
    )


def _normalize_title(value: str | None, *, fallback: str) -> str:
    text = (value or "").strip()
    return text or fallback
