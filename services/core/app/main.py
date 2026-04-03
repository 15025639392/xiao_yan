from collections.abc import Generator
from contextlib import asynccontextmanager
from threading import Event, Thread

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_memory_storage_path
from app.agent.loop import AutonomyLoop
from app.llm.gateway import ChatGateway
from app.llm.schemas import (
    ChatHistoryMessage,
    ChatHistoryResponse,
    ChatMessage,
    ChatRequest,
    ChatResult,
)
from app.memory.models import MemoryEvent
from app.memory.repository import FileMemoryRepository, MemoryRepository
from app.runtime import StateStore


@asynccontextmanager
async def lifespan(app: FastAPI):
    _ensure_runtime_initialized(app)

    try:
        yield
    finally:
        stop_event = app.state.stop_event
        worker = app.state.autonomy_thread
        if worker.is_alive():
            stop_event.set()
            worker.join(timeout=1.0)


app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5173",
        "http://localhost:5173",
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _ensure_runtime_initialized(target_app: FastAPI) -> None:
    if hasattr(target_app.state, "state_store"):
        return

    state_store = StateStore()
    memory_repository = FileMemoryRepository(get_memory_storage_path())
    stop_event = Event()
    loop = AutonomyLoop(state_store, memory_repository)

    def run_loop() -> None:
        while not stop_event.wait(5.0):
            loop.tick_once()

    worker = Thread(target=run_loop, name="autonomy-loop", daemon=True)
    worker.start()

    target_app.state.state_store = state_store
    target_app.state.memory_repository = memory_repository
    target_app.state.stop_event = stop_event
    target_app.state.autonomy_thread = worker


def get_chat_gateway() -> Generator[ChatGateway, None, None]:
    gateway = ChatGateway.from_env()
    try:
        yield gateway
    finally:
        gateway.close()


def get_memory_repository() -> MemoryRepository:
    _ensure_runtime_initialized(app)
    return app.state.memory_repository


def get_state_store() -> StateStore:
    _ensure_runtime_initialized(app)
    return app.state.state_store


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


@app.get("/state")
def get_state(
    state_store: StateStore = Depends(get_state_store),
) -> dict:
    return state_store.get().model_dump()


@app.get("/messages")
def get_messages(
    memory_repository: MemoryRepository = Depends(get_memory_repository),
) -> ChatHistoryResponse:
    recent_events = list(reversed(memory_repository.list_recent(limit=20)))
    messages = [
        ChatHistoryMessage(role=event.role, content=event.content)
        for event in recent_events
        if event.kind == "chat" and event.role in {"user", "assistant"}
    ]
    return ChatHistoryResponse(messages=messages)


@app.post("/lifecycle/wake")
def wake() -> dict:
    return get_state_store().wake().model_dump()


@app.post("/lifecycle/sleep")
def sleep() -> dict:
    return get_state_store().sleep().model_dump()


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
