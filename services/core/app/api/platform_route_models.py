from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.llm.schemas import ChatSubmissionResult
from app.platform_adapters.models import (
    CoreDecision,
    CoreDecisionDraft,
    CoreDecisionKind,
    InternalDecisionInput,
)


class PlatformPreviewRequest(BaseModel):
    platform: str
    raw_payload: dict[str, Any] = Field(default_factory=dict)
    decision: CoreDecision


class PlatformListResponse(BaseModel):
    platforms: list[str]


class PlatformInternalPreviewRequest(BaseModel):
    platform: str
    raw_payload: dict[str, Any] = Field(default_factory=dict)
    internal_decision: InternalDecisionInput


class ChatSubmissionPreviewRequest(BaseModel):
    platform: str
    raw_payload: dict[str, Any] = Field(default_factory=dict)
    submission: ChatSubmissionResult
    output_text: str
    preferred_kind: CoreDecisionKind | None = None
    summary: str | None = None
    supporting_points: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class PlatformDraftPreviewRequest(BaseModel):
    platform: str
    raw_payload: dict[str, Any] = Field(default_factory=dict)
    decision_draft: CoreDecisionDraft


class PlatformChatPreviewRequest(BaseModel):
    platform: str
    raw_payload: dict[str, Any] = Field(default_factory=dict)
    message: str | None = None
    preferred_kind: CoreDecisionKind | None = None


class XiaohongshuAuthorSnapshot(BaseModel):
    id: str
    name: str | None = None
    bio: str | None = None


class XiaohongshuNoteSnapshot(BaseModel):
    note_id: str
    title: str | None = None
    note_text: str = ""
    topic: str | None = None
    source_scene: str | None = None
    published_at: str | None = None
    source_url: str | None = None
    author: XiaohongshuAuthorSnapshot


class XiaohongshuCommentSnapshot(BaseModel):
    comment_id: str
    note_id: str
    comment_text: str
    source_scene: str | None = None
    commented_at: str | None = None
    source_url: str | None = None
    note_title: str | None = None
    note_text: str | None = None
    topic: str | None = None
    author: XiaohongshuAuthorSnapshot


class XiaohongshuImportPreviewRequest(BaseModel):
    item_type: str
    note: XiaohongshuNoteSnapshot | None = None
    comment: XiaohongshuCommentSnapshot | None = None
    message: str | None = None


class XiaohongshuImportFilePreviewRequest(BaseModel):
    path: str


class XiaohongshuImportBatchItem(BaseModel):
    index: int
    item_type: str
    request: XiaohongshuImportPreviewRequest


class XiaohongshuNotificationEntrySnapshot(BaseModel):
    entry_id: str
    actor_name: str | None = None
    actor_id: str | None = None
    actor_bio: str | None = None
    comment_text: str
    note_id: str
    note_title: str | None = None
    note_text: str | None = None
    topic: str | None = None
    occurred_at: str | None = None
    source_url: str | None = None


class XiaohongshuNotificationPreviewRequest(BaseModel):
    entries: list[XiaohongshuNotificationEntrySnapshot] = Field(default_factory=list)
    message: str | None = None


class XiaohongshuTopicOpportunitySnapshot(BaseModel):
    topic: str
    participation_count: str | None = None
    view_count: str | None = None


class XiaohongshuActivityOpportunitySnapshot(BaseModel):
    title: str
    date_range: str | None = None
    incentive_hint: str | None = None


class XiaohongshuCreatorHomePreviewRequest(BaseModel):
    account_name: str | None = None
    topics: list[XiaohongshuTopicOpportunitySnapshot] = Field(default_factory=list)
    activities: list[XiaohongshuActivityOpportunitySnapshot] = Field(default_factory=list)
    message: str | None = None


class XiaohongshuCreatorHomeCaptureResponse(BaseModel):
    source_url: str
    account_name: str | None = None
    raw_text: str
    topics: list[XiaohongshuTopicOpportunitySnapshot] = Field(default_factory=list)
    activities: list[XiaohongshuActivityOpportunitySnapshot] = Field(default_factory=list)


class XiaohongshuImageCardDraftItem(BaseModel):
    title: str
    body: str


class XiaohongshuStructuredPublishDraft(BaseModel):
    title: str
    opening: str
    body_sections: list[str] = Field(default_factory=list)
    closing_cta: str
    first_comment: str
    image_cards: list[XiaohongshuImageCardDraftItem] = Field(default_factory=list)


class XiaohongshuCoverPreviewRequest(BaseModel):
    title: str
    body: str
    template_name: str | None = None


class XiaohongshuCoverPreviewResponse(BaseModel):
    title: str
    body: str
    template_name: str
    available_templates: list[str] = Field(default_factory=list)
    image_path: str
    image_data_url: str


class XiaohongshuLeadCaptureRequest(BaseModel):
    title_hint: str | None = None


class XiaohongshuLeadCaptureResponse(BaseModel):
    source_url: str
    note_title: str
    raw_text: str
    like_count: str | None = None
    collect_count: str | None = None
    comment_count: str | None = None
    share_count: str | None = None
    direct_message_signal_count: int = 0
    wechat_signal_count: int = 0
    purchase_signal_count: int = 0
    lead_keywords: list[str] = Field(default_factory=list)
    matched_comment_lines: list[str] = Field(default_factory=list)
    tracking_template: str
    message: str
