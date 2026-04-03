from collections.abc import Generator

from fastapi import Depends, FastAPI

from app.llm.gateway import ChatGateway
from app.llm.schemas import ChatMessage, ChatRequest, ChatResult
from app.usecases.lifecycle import go_to_sleep, wake_up

app = FastAPI()


def get_chat_gateway() -> Generator[ChatGateway, None, None]:
    gateway = ChatGateway.from_env()
    try:
        yield gateway
    finally:
        gateway.close()


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
) -> ChatResult:
    return gateway.create_response([ChatMessage(role="user", content=request.message)])
