from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4

from pydantic import BaseModel, Field


class GoalStatus(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    ABANDONED = "abandoned"


class Goal(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    title: str
    source: str | None = None
    chain_id: str | None = None
    parent_goal_id: str | None = None
    generation: int = 0
    status: GoalStatus = GoalStatus.ACTIVE
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class GoalStatusUpdate(BaseModel):
    status: GoalStatus
