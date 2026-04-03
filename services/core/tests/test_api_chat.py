from fastapi.testclient import TestClient

from app.llm.schemas import ChatMessage
from app.llm.gateway import GatewayResponse
from app.main import app, get_chat_gateway, get_memory_repository
from app.memory.models import MemoryEvent
from app.memory.repository import InMemoryMemoryRepository


class StubGateway:
    def __init__(self) -> None:
        self.last_messages: list[ChatMessage] = []

    def create_response(self, messages, instructions=None) -> GatewayResponse:
        self.last_messages = list(messages)
        return GatewayResponse(
            response_id="resp_test",
            output_text=f"echo:{messages[-1].content}",
        )

    def close(self) -> None:
        return None


def test_post_chat_returns_gateway_response():
    memory_repository = InMemoryMemoryRepository()
    gateway = StubGateway()

    def override_gateway():
        try:
            yield gateway
        finally:
            gateway.close()

    def override_memory_repository():
        return memory_repository

    app.dependency_overrides[get_chat_gateway] = override_gateway
    app.dependency_overrides[get_memory_repository] = override_memory_repository

    try:
        client = TestClient(app)
        response = client.post("/chat", json={"message": "hello"})
        assert response.status_code == 200
        assert response.json() == {
            "response_id": "resp_test",
            "output_text": "echo:hello",
        }
        recent = memory_repository.list_recent(limit=5)
        assert [event.role for event in reversed(recent)] == ["user", "assistant"]
        assert [event.content for event in reversed(recent)] == ["hello", "echo:hello"]
    finally:
        app.dependency_overrides.clear()


def test_post_chat_includes_recent_memory_in_gateway_messages():
    memory_repository = InMemoryMemoryRepository()
    memory_repository.save_event(
        MemoryEvent(kind="chat", role="user", content="昨天我们聊了星星")
    )
    memory_repository.save_event(
        MemoryEvent(kind="chat", role="assistant", content="我记得你喜欢夜空")
    )
    gateway = StubGateway()

    def override_gateway():
        try:
            yield gateway
        finally:
            gateway.close()

    def override_memory_repository():
        return memory_repository

    app.dependency_overrides[get_chat_gateway] = override_gateway
    app.dependency_overrides[get_memory_repository] = override_memory_repository

    try:
        client = TestClient(app)
        response = client.post("/chat", json={"message": "今天还记得吗"})
        assert response.status_code == 200
        assert [(message.role, message.content) for message in gateway.last_messages] == [
            ("user", "昨天我们聊了星星"),
            ("assistant", "我记得你喜欢夜空"),
            ("user", "今天还记得吗"),
        ]
    finally:
        app.dependency_overrides.clear()
