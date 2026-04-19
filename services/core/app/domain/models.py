from datetime import datetime
from enum import Enum

from pydantic import BaseModel
from app.focus.models import FocusEffort
from app.tools.models import ToolExecutionResult


class WakeMode(str, Enum):
    AWAKE = "awake"
    SLEEPING = "sleeping"


class FocusMode(str, Enum):
    SLEEPING = "sleeping"
    AUTONOMY = "autonomy"


class FocusSubject(BaseModel):
    kind: str
    title: str
    why_now: str
    source_ref: str | None = None
    goal_id: str | None = None


class BeingState(BaseModel):
    mode: WakeMode
    focus_mode: FocusMode = FocusMode.SLEEPING
    current_thought: str | None = None
    focus_subject: FocusSubject | None = None
    focus_effort: FocusEffort | None = None
    last_action: ToolExecutionResult | None = None
    last_proactive_source: str | None = None
    last_proactive_at: datetime | None = None

    @classmethod
    def default(cls) -> "BeingState":
        return cls(mode=WakeMode.SLEEPING)
