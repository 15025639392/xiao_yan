from datetime import datetime

from pydantic import BaseModel

from app.domain.models import BeingState


class NextAction(BaseModel):
    kind: str
    reason: str


def choose_next_action(
    state: BeingState,
    pending_goals: list[str],
    recent_events: list[str],
    cooldown_ready: bool,
    now: datetime,
) -> NextAction:
    if pending_goals:
        return NextAction(kind="act", reason="存在未完成目标")
    if not cooldown_ready:
        return NextAction(kind="idle", reason="主动冷却中")
    return NextAction(kind="reflect", reason="当前没有待执行目标")
