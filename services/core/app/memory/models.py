from pydantic import BaseModel


class MemoryEvent(BaseModel):
    kind: str
    content: str
