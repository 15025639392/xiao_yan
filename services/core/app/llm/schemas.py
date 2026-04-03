from pydantic import BaseModel


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str


class ChatResult(BaseModel):
    response_id: str | None = None
    output_text: str
