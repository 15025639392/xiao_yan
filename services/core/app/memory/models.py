from datetime import datetime, timezone

from pydantic import BaseModel, Field


class MemoryEvent(BaseModel):
    kind: str
    content: str
    role: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
