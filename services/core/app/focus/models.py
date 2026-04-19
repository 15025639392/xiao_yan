from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field


class FocusEffort(BaseModel):
    focus_title: str
    why_now: str
    action_kind: str
    did_what: str
    effect: str | None = None
    next_hint: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
