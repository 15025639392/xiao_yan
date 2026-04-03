from pydantic import BaseModel


class WorldState(BaseModel):
    time_of_day: str
    energy: str
    mood: str
    focus_tension: str
