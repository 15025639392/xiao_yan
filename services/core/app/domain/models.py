from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class WakeMode(str, Enum):
    AWAKE = "awake"
    SLEEPING = "sleeping"


class BeingState(BaseModel):
    mode: WakeMode
    current_thought: str | None = None
    active_goal_ids: list[str] = Field(default_factory=list)
    last_proactive_source: str | None = None
    last_proactive_at: datetime | None = None

    @classmethod
    def default(cls) -> "BeingState":
        return cls(mode=WakeMode.SLEEPING)
