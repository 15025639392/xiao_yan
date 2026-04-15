from typing import Any, Literal

from pydantic import BaseModel, Field


class ChatAttachment(BaseModel):
    type: Literal["folder", "file", "image"]
    path: str
    name: str | None = None
    mime_type: str | None = None


class ChatMessage(BaseModel):
    role: str
    content: str | list[dict[str, Any] | str]


class ChatRequest(BaseModel):
    message: str
    attachments: list[ChatAttachment] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    mcp_servers: list[str] = Field(default_factory=list)


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
    id: str
    role: str
    content: str
    created_at: str | None = None
    session_id: str | None = None


class ChatHistoryResponse(BaseModel):
    messages: list[ChatHistoryMessage]
    limit: int | None = None
    offset: int | None = None
    has_more: bool | None = None
    next_offset: int | None = None
