from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4

from pydantic import BaseModel, Field


class GoalStatus(str, Enum):
    ACTIVE = "active"
    COMPLETED = "completed"


class Goal(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    title: str
    source: str | None = None
    status: GoalStatus = GoalStatus.ACTIVE
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

