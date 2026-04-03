from fastapi.testclient import TestClient

from app.llm.gateway import GatewayResponse
from app.main import app, get_chat_gateway, get_memory_repository
from app.memory.repository import InMemoryMemoryRepository


class StubGateway:
    def create_response(self, messages, instructions=None) -> GatewayResponse:
        return GatewayResponse(
            response_id="resp_test",
            output_text=f"echo:{messages[0].content}",
        )

    def close(self) -> None:
        return None


def test_post_chat_returns_gateway_response():
    memory_repository = InMemoryMemoryRepository()

    def override_gateway():
        gateway = StubGateway()
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
