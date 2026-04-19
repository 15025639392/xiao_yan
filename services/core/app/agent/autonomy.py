from datetime import datetime

from pydantic import BaseModel

from app.domain.models import BeingState


class NextAction(BaseModel):
    kind: str
    reason: str


class FocusSummary(BaseModel):
    focus_title: str
    stage: str = "direct"


def choose_next_action(
    state: BeingState,
    has_focus_subject: bool,
    focus_summary: FocusSummary | None,
    recent_events: list[str],
    cooldown_ready: bool,
    now: datetime,
) -> NextAction:
    if state.focus_subject is not None:
        if focus_summary is not None and focus_summary.stage == "consolidate" and cooldown_ready:
            return NextAction(kind="consolidate", reason="当前牵挂进入收束阶段")
        return NextAction(kind="act", reason="当前仍有明确牵挂挂在眼前")
    if has_focus_subject:
        if focus_summary is not None and focus_summary.stage == "consolidate" and cooldown_ready:
            return NextAction(kind="consolidate", reason="当前牵挂进入收束阶段")
        return NextAction(kind="act", reason="当前仍有持续中的牵挂")
    if not cooldown_ready:
        return NextAction(kind="idle", reason="主动冷却中")
    return NextAction(kind="reflect", reason="当前没有待承接的牵挂")
