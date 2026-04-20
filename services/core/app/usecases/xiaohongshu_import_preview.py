from __future__ import annotations

from pydantic import BaseModel

from app.api.platform_route_models import (
    XiaohongshuCommentSnapshot,
    XiaohongshuImportPreviewRequest,
    XiaohongshuNoteSnapshot,
)
from app.platform_adapters.models import CoreDecisionKind


class XiaohongshuImportEnvelope(BaseModel):
    raw_payload: dict
    preferred_kind: CoreDecisionKind
    message: str | None = None


def build_xiaohongshu_import_envelope(
    request_body: XiaohongshuImportPreviewRequest,
) -> XiaohongshuImportEnvelope:
    item_type = request_body.item_type.strip().lower()
    if item_type == "comment":
        if request_body.comment is None:
            raise ValueError("xiaohongshu comment snapshot is required")
        return _build_comment_envelope(request_body.comment, request_body.message)
    if item_type == "note":
        if request_body.note is None:
            raise ValueError("xiaohongshu note snapshot is required")
        return _build_note_envelope(request_body.note, request_body.message)
    raise ValueError("xiaohongshu item_type must be 'comment' or 'note'")


def _build_comment_envelope(
    comment: XiaohongshuCommentSnapshot,
    message: str | None,
) -> XiaohongshuImportEnvelope:
    raw_payload = {
        "comment_id": comment.comment_id,
        "note_id": comment.note_id,
        "comment_text": comment.comment_text,
        "source_scene": comment.source_scene,
        "occurred_at": comment.commented_at,
        "source_url": comment.source_url,
        "topic": comment.topic,
        "note_title": comment.note_title,
        "note_text": comment.note_text,
        "author": comment.author.model_dump(mode="json"),
    }
    default_message = message or _build_comment_message(comment)
    return XiaohongshuImportEnvelope(
        raw_payload=raw_payload,
        preferred_kind="comment_reply",
        message=default_message,
    )


def _build_note_envelope(
    note: XiaohongshuNoteSnapshot,
    message: str | None,
) -> XiaohongshuImportEnvelope:
    raw_payload = {
        "note_id": note.note_id,
        "note_text": note.note_text,
        "title": note.title,
        "topic": note.topic,
        "source_scene": note.source_scene,
        "published_at": note.published_at,
        "source_url": note.source_url,
        "author": note.author.model_dump(mode="json"),
    }
    default_message = message or _build_note_message(note)
    return XiaohongshuImportEnvelope(
        raw_payload=raw_payload,
        preferred_kind="note_draft",
        message=default_message,
    )


def _build_comment_message(comment: XiaohongshuCommentSnapshot) -> str:
    note_title = (comment.note_title or "").strip()
    note_text = (comment.note_text or "").strip()
    title_line = f"笔记标题：{note_title}\n" if note_title else ""
    text_line = f"笔记内容摘要：{note_text}\n" if note_text else ""
    return (
        "这是一次小红书评论导入，请生成一条适合人工确认后发送的评论回复候选。"
        "保持真诚、轻量、不过度营销。\n"
        f"{title_line}"
        f"{text_line}"
        f"评论内容：{comment.comment_text}"
    ).strip()


def _build_note_message(note: XiaohongshuNoteSnapshot) -> str:
    title_line = f"当前标题：{note.title}\n" if (note.title or "").strip() else ""
    topic_line = f"话题：{note.topic}\n" if (note.topic or "").strip() else ""
    return (
        "这是一次小红书笔记素材导入，请生成一版适合人工确认后发布的笔记草稿。"
        "先稳住标题和主线，不要写成流水账。\n"
        f"{title_line}"
        f"{topic_line}"
        f"素材内容：{note.note_text}"
    ).strip()
