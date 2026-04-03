from fastapi.testclient import TestClient

from app.llm.gateway import GatewayResponse
from app.main import app, get_chat_gateway


class StubGateway:
    def create_response(self, messages, instructions=None) -> GatewayResponse:
        return GatewayResponse(
            response_id="resp_test",
            output_text=f"echo:{messages[0].content}",
        )

    def close(self) -> None:
        return None


def test_post_chat_returns_gateway_response():
    def override_gateway():
        gateway = StubGateway()
        try:
            yield gateway
        finally:
            gateway.close()

    app.dependency_overrides[get_chat_gateway] = override_gateway

    try:
        client = TestClient(app)
        response = client.post("/chat", json={"message": "hello"})
        assert response.status_code == 200
        assert response.json() == {
            "response_id": "resp_test",
            "output_text": "echo:hello",
        }
    finally:
        app.dependency_overrides.clear()
