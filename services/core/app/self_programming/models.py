from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class SelfProgrammingTrigger(str, Enum):
    HARD_FAILURE = "hard_failure"
    PROACTIVE = "proactive"


class SelfProgrammingCandidate(BaseModel):
    trigger: SelfProgrammingTrigger
    reason: str
    target_area: str
    spec: str
    test_commands: list[str] = Field(default_factory=list)
    created_at: datetime | None = None
