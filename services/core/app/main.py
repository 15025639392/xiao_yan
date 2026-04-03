from collections.abc import Generator

from fastapi import Depends, FastAPI

from app.config import get_memory_storage_path
from app.llm.gateway import ChatGateway
from app.llm.schemas import ChatMessage, ChatRequest, ChatResult
from app.memory.models import MemoryEvent
from app.memory.repository import FileMemoryRepository, MemoryRepository
from app.usecases.lifecycle import go_to_sleep, wake_up

app = FastAPI()


def get_chat_gateway() -> Generator[ChatGateway, None, None]:
    gateway = ChatGateway.from_env()
    try:
        yield gateway
    finally:
        gateway.close()


def get_memory_repository() -> MemoryRepository:
    return FileMemoryRepository(get_memory_storage_path())


def build_chat_messages(
    memory_repository: MemoryRepository,
    user_message: str,
    limit: int = 6,
) -> list[ChatMessage]:
    relevant_events = memory_repository.search_relevant(user_message, limit=limit)
    messages = [
        ChatMessage(role=event.role, content=event.content)
        for event in relevant_events
        if event.kind == "chat" and event.role in {"user", "assistant"}
    ]
    messages.append(ChatMessage(role="user", content=user_message))
    return messages


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/lifecycle/wake")
def wake() -> dict:
    return wake_up().model_dump()


@app.post("/lifecycle/sleep")
def sleep() -> dict:
    return go_to_sleep().model_dump()


@app.post("/chat")
def chat(
    request: ChatRequest,
    gateway: ChatGateway = Depends(get_chat_gateway),
    memory_repository: MemoryRepository = Depends(get_memory_repository),
) -> ChatResult:
    result = gateway.create_response(
        build_chat_messages(memory_repository, request.message)
    )
    memory_repository.save_event(
        MemoryEvent(
            kind="chat",
            role="user",
            content=request.message,
        )
    )
    memory_repository.save_event(
        MemoryEvent(
            kind="chat",
            role="assistant",
            content=result.output_text,
        )
    )
    return result
