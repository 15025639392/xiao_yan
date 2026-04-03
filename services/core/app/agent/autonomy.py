from datetime import datetime

from pydantic import BaseModel

from app.domain.models import BeingState


class NextAction(BaseModel):
    kind: str
    reason: str


class GoalFocusSummary(BaseModel):
    goal_title: str
    chain_id: str | None = None
    chain_length: int | None = None
    chain_generation: int | None = None
    stage: str = "direct"


def choose_next_action(
    state: BeingState,
    pending_goals: list[str],
    focus_summary: GoalFocusSummary | None,
    recent_events: list[str],
    cooldown_ready: bool,
    now: datetime,
) -> NextAction:
    if pending_goals:
        if focus_summary is not None and focus_summary.stage == "consolidate" and cooldown_ready:
            return NextAction(kind="consolidate", reason="目标链进入收束阶段")
        return NextAction(kind="act", reason="存在未完成目标")
    if not cooldown_ready:
        return NextAction(kind="idle", reason="主动冷却中")
    return NextAction(kind="reflect", reason="当前没有待执行目标")
