from typing import Any, Literal

from pydantic import BaseModel, Field


class ChatReasoningRequest(BaseModel):
    enabled: bool = False
    session_id: str | None = None


class ChatReasoningState(BaseModel):
    session_id: str
    phase: Literal["planning", "exploring", "finalizing", "completed"] = "planning"
    step_index: int = Field(default=1, ge=1)
    summary: str = ""
    updated_at: str


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
    request_key: str | None = None
    user_timezone: str | None = None
    user_local_time: str | None = None
    user_time_of_day: Literal["morning", "afternoon", "evening", "night"] | None = None
    attachments: list[ChatAttachment] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    mcp_servers: list[str] = Field(default_factory=list)
    reasoning: ChatReasoningRequest | None = None


class ChatResumeRequest(BaseModel):
    message: str
    assistant_message_id: str
    partial_content: str
    request_key: str | None = None
    reasoning_session_id: str | None = None
    user_timezone: str | None = None
    user_local_time: str | None = None
    user_time_of_day: Literal["morning", "afternoon", "evening", "night"] | None = None


class ChatResult(BaseModel):
    response_id: str | None = None
    output_text: str


class ChatSubmissionResult(BaseModel):
    response_id: str | None = None
    assistant_message_id: str
    request_key: str | None = None
    reasoning_session_id: str | None = None
    reasoning_state: ChatReasoningState | None = None


class ChatHistoryMessage(BaseModel):
    id: str
    role: str
    content: str
    created_at: str | None = None
    session_id: str | None = None
    request_key: str | None = None
    reasoning_session_id: str | None = None
    reasoning_state: ChatReasoningState | None = None


class ChatHistoryResponse(BaseModel):
    messages: list[ChatHistoryMessage]
    limit: int | None = None
    offset: int | None = None
    has_more: bool | None = None
    next_offset: int | None = None
