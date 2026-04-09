from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from app.domain.models import OrchestratorPlan, OrchestratorSession, OrchestratorTask, OrchestratorVerification


class OrchestratorMessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class OrchestratorMessageState(str, Enum):
    STREAMING = "streaming"
    COMPLETED = "completed"
    FAILED = "failed"


class OrchestratorMessageBlock(BaseModel):
    type: str
    text: str | None = None
    plan: OrchestratorPlan | None = None
    task: OrchestratorTask | None = None
    verification: OrchestratorVerification | None = None
    session: OrchestratorSession | None = None
    summary: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class OrchestratorMessage(BaseModel):
    message_id: str = Field(default_factory=lambda: f"orchmsg_{uuid4().hex}")
    session_id: str
    role: OrchestratorMessageRole
    blocks: list[OrchestratorMessageBlock] = Field(default_factory=list)
    state: OrchestratorMessageState = OrchestratorMessageState.COMPLETED
    created_at: datetime = Field(default_factory=datetime.utcnow)
    related_task_id: str | None = None


class OrchestratorChatSubmissionResult(BaseModel):
    session_id: str
    assistant_message_id: str
