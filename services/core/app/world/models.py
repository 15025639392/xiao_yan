from pydantic import BaseModel


class WorldState(BaseModel):
    time_of_day: str
