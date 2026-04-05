from pydantic import BaseModel


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str


class ChatResumeRequest(BaseModel):
    message: str
    assistant_message_id: str
    partial_content: str


class ChatResult(BaseModel):
    response_id: str | None = None
    output_text: str


class ChatSubmissionResult(BaseModel):
    response_id: str | None = None
    assistant_message_id: str


class ChatHistoryMessage(BaseModel):
    role: str
    content: str


class ChatHistoryResponse(BaseModel):
    messages: list[ChatHistoryMessage]
