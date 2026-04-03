from datetime import datetime

from pydantic import BaseModel


class WorldState(BaseModel):
    time_of_day: str
    energy: str
    mood: str
    focus_tension: str
    latest_event: str | None = None
    latest_event_at: datetime | None = None
