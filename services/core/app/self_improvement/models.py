from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class SelfImprovementTrigger(str, Enum):
    HARD_FAILURE = "hard_failure"
    PROACTIVE = "proactive"


class SelfImprovementCandidate(BaseModel):
    trigger: SelfImprovementTrigger
    reason: str
    target_area: str
    spec: str
    test_commands: list[str] = Field(default_factory=list)
    created_at: datetime | None = None
