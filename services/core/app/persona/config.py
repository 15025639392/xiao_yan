from pydantic import BaseModel, Field


class PersonaConfig(BaseModel):
    name: str
    identity: str
    values: list[str] = Field(default_factory=list)
