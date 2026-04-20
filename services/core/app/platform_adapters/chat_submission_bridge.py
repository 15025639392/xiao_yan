from __future__ import annotations

from app.llm.schemas import ChatSubmissionResult
from app.platform_adapters.models import CoreDecisionDraft, CoreDecisionKind


def build_decision_draft_from_chat_submission(
    *,
    submission: ChatSubmissionResult,
    output_text: str,
    preferred_kind: CoreDecisionKind | None = None,
    summary: str | None = None,
    supporting_points: list[str] | None = None,
    metadata: dict | None = None,
) -> CoreDecisionDraft:
    normalized_text = (output_text or "").strip()
    if not normalized_text:
        raise ValueError("chat submission output_text cannot be blank")
    kind = preferred_kind or "reply_suggestion"
    return CoreDecisionDraft(
        kind=kind,
        text=normalized_text,
        summary=summary,
        supporting_points=[point.strip() for point in (supporting_points or []) if point.strip()],
        request_key=submission.request_key,
        assistant_message_id=submission.assistant_message_id,
        reasoning_session_id=submission.reasoning_session_id,
        metadata=dict(metadata or {}),
    )
