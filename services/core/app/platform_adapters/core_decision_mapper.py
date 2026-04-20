from __future__ import annotations

from app.platform_adapters.models import (
    CanonicalEvent,
    CoreDecision,
    CoreDecisionDraft,
    CoreDecisionKind,
    InternalDecisionInput,
)


class CoreDecisionMapper:
    def map_from_internal(
        self,
        *,
        platform: str,
        event: CanonicalEvent,
        decision_input: InternalDecisionInput,
    ) -> CoreDecision:
        normalized_text = (decision_input.output_text or "").strip()
        if not normalized_text:
            raise ValueError("internal decision output_text cannot be blank")

        kind = decision_input.preferred_kind or self._default_kind(platform=platform, event=event)
        supporting_points = [point.strip() for point in decision_input.supporting_points if point.strip()]
        return CoreDecision(
            kind=kind,
            summary=decision_input.summary,
            primary_text=normalized_text,
            supporting_points=supporting_points,
            metadata={
                "source": decision_input.source,
                "request_key": decision_input.request_key,
                "assistant_message_id": decision_input.assistant_message_id,
                "reasoning_session_id": decision_input.reasoning_session_id,
                **decision_input.metadata,
            },
        )

    def map_from_draft(
        self,
        *,
        decision_draft: CoreDecisionDraft,
    ) -> CoreDecision:
        normalized_text = (decision_draft.text or "").strip()
        if not normalized_text:
            raise ValueError("core decision draft text cannot be blank")
        return CoreDecision(
            kind=decision_draft.kind,
            summary=decision_draft.summary,
            primary_text=normalized_text,
            supporting_points=[point.strip() for point in decision_draft.supporting_points if point.strip()],
            metadata={
                "source": "core_decision_draft",
                "request_key": decision_draft.request_key,
                "assistant_message_id": decision_draft.assistant_message_id,
                "reasoning_session_id": decision_draft.reasoning_session_id,
                **decision_draft.metadata,
            },
        )

    def _default_kind(self, *, platform: str, event: CanonicalEvent) -> CoreDecisionKind:
        if platform == "xiaohongshu":
            return "comment_reply" if event.event_type == "comment" else "note_draft"
        if platform == "wechat_manual":
            scene = str(event.metadata.get("scene") or "").strip().lower()
            if "follow" in scene:
                return "follow_up_suggestion"
            return "reply_suggestion"
        return "reply_suggestion"
