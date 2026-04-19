from __future__ import annotations

from dataclasses import dataclass

from app.domain.models import BeingState, FocusSubject


@dataclass(slots=True)
class FocusContext:
    focus_title: str
    source_kind: str
    source_label: str
    reason_kind: str
    reason_label: str

    def render_for_prompt(self) -> str:
        return f"当前焦点来自{self.source_label}，之所以现在还挂在眼前，是因为{self.reason_label}。"

    def to_payload(self) -> dict[str, str]:
        return {
            "focus_title": self.focus_title,
            "source_kind": self.source_kind,
            "source_label": self.source_label,
            "reason_kind": self.reason_kind,
            "reason_label": self.reason_label,
            "prompt_summary": self.render_for_prompt(),
        }


def build_focus_context(
    *,
    state: BeingState,
) -> FocusContext | None:
    if state.focus_subject is not None:
        focus_context = _focus_subject_context(state.focus_subject)
        if focus_context is not None:
            return focus_context
    return None


def _focus_subject_context(
    focus_subject: FocusSubject,
) -> FocusContext | None:
    if focus_subject.kind == "focus_trace":
        reason_kind, reason_label = _reason_descriptor_from_subject(focus_subject)
        return FocusContext(
            focus_title=focus_subject.title,
            source_kind="focus_trace",
            source_label="一条挂在手上、但不等于目标本身的推进线索",
            reason_kind=reason_kind,
            reason_label=reason_label,
        )

    if focus_subject.kind == "user_topic":
        return FocusContext(
            focus_title=focus_subject.title,
            source_kind="user_topic_focus",
            source_label="刚被你这轮话题重新牵动的事",
            reason_kind="user_topic_lingering",
            reason_label=focus_subject.why_now,
        )

    if focus_subject.kind == "lingering":
        return FocusContext(
            focus_title=focus_subject.title,
            source_kind="lingering_focus",
            source_label="刚发生过、但心里还没完全放下的事",
            reason_kind="lingering_attention",
            reason_label=focus_subject.why_now,
        )

    return FocusContext(
        focus_title=focus_subject.title,
        source_kind="active_focus",
        source_label="她此刻正在挂着的事",
        reason_kind="active_focus_reason",
        reason_label=focus_subject.why_now,
    )


def _reason_descriptor_from_subject(focus_subject: FocusSubject) -> tuple[str, str]:
    if focus_subject.why_now.strip():
        return "focus_subject_reason", focus_subject.why_now
    return "focus_still_active", "这件事还没完成，也还没有暂停或放下"
