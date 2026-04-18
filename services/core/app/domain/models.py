from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, field_validator
from app.focus.models import FocusEffort
from app.tools.models import ToolExecutionResult


class WakeMode(str, Enum):
    AWAKE = "awake"
    SLEEPING = "sleeping"


class FocusMode(str, Enum):
    SLEEPING = "sleeping"
    MORNING_PLAN = "morning_plan"
    AUTONOMY = "autonomy"


class TodayPlanStepStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"


class TodayPlanStepKind(str, Enum):
    REFLECT = "reflect"
    ACTION = "action"


class TodayPlanStep(BaseModel):
    content: str
    status: TodayPlanStepStatus = TodayPlanStepStatus.PENDING
    kind: TodayPlanStepKind = TodayPlanStepKind.REFLECT
    command: str | None = None


class TodayPlan(BaseModel):
    goal_id: str
    goal_title: str
    steps: list[TodayPlanStep] = Field(default_factory=list)


class BeingState(BaseModel):
    mode: WakeMode
    focus_mode: FocusMode = FocusMode.SLEEPING
    current_thought: str | None = None
    active_goal_ids: list[str] = Field(default_factory=list)
    today_plan: TodayPlan | None = None
    focus_effort: FocusEffort | None = None
    last_action: ToolExecutionResult | None = None
    last_proactive_source: str | None = None
    last_proactive_at: datetime | None = None

    @field_validator("focus_mode", mode="before")
    @classmethod
    def _normalize_legacy_focus_mode(cls, value):
        if value == "orchestrator":
            return FocusMode.AUTONOMY
        return value

    @classmethod
    def default(cls) -> "BeingState":
        return cls(mode=WakeMode.SLEEPING)
