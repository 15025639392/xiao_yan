from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


PlatformName = Literal["wechat_manual", "xiaohongshu", "wechat_official"]
CanonicalEventType = Literal["message", "comment", "post", "unknown"]
CoreDecisionKind = Literal[
    "reply_suggestion",
    "follow_up_suggestion",
    "comment_reply",
    "note_draft",
]
CoreDecisionSource = Literal["assistant_text", "chat_submission"]
PlatformActionType = Literal[
    "reply_suggestion",
    "follow_up_suggestion",
    "comment_reply_candidate",
    "note_draft_candidate",
]
DeliveryStatus = Literal["drafted", "simulated", "skipped"]
LeadIntentLevel = Literal["low", "medium", "high"]
LeadStage = Literal["ignore", "observe", "engage", "follow_up"]
SuggestedAction = Literal["ignore", "reply_comment", "prepare_note", "follow_up_manually"]


class CanonicalUser(BaseModel):
    platform: PlatformName
    user_id: str
    display_name: str | None = None
    profile_hint: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class CanonicalEvent(BaseModel):
    platform: PlatformName
    event_id: str
    event_type: CanonicalEventType = "unknown"
    thread_id: str
    occurred_at: datetime | None = None
    text: str = ""
    user: CanonicalUser
    raw_payload: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class CoreDecision(BaseModel):
    kind: CoreDecisionKind
    summary: str | None = None
    primary_text: str
    supporting_points: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class CoreDecisionDraft(BaseModel):
    kind: CoreDecisionKind
    text: str
    summary: str | None = None
    supporting_points: list[str] = Field(default_factory=list)
    request_key: str | None = None
    assistant_message_id: str | None = None
    reasoning_session_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class InternalDecisionInput(BaseModel):
    source: CoreDecisionSource = "assistant_text"
    output_text: str
    preferred_kind: CoreDecisionKind | None = None
    summary: str | None = None
    supporting_points: list[str] = Field(default_factory=list)
    request_key: str | None = None
    assistant_message_id: str | None = None
    reasoning_session_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class PlatformAction(BaseModel):
    platform: PlatformName
    action_type: PlatformActionType
    target_thread_id: str
    title: str | None = None
    content: str
    delivery_mode: Literal["draft", "simulate"] = "draft"
    metadata: dict[str, Any] = Field(default_factory=dict)


class DeliveryResult(BaseModel):
    platform: PlatformName
    action_type: PlatformActionType
    status: DeliveryStatus
    target_thread_id: str
    reference_id: str | None = None
    message: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class PlatformProcessResult(BaseModel):
    event: CanonicalEvent
    user: CanonicalUser
    actions: list[PlatformAction]
    delivery_results: list[DeliveryResult]


class LeadAssessment(BaseModel):
    platform: PlatformName
    is_lead: bool
    intent_level: LeadIntentLevel
    lead_stage: LeadStage
    suggested_action: SuggestedAction
    follow_up_hint: str | None = None
    reasons: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
