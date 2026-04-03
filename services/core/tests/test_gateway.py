import json

import httpx

from app.llm.gateway import ChatGateway
from app.llm.schemas import ChatMessage


def test_gateway_normalizes_messages():
    gateway = ChatGateway(api_key="test-key", model="gpt-5.4")
    payload = gateway.build_payload([ChatMessage(role="user", content="hi")])
    assert payload["model"] == "gpt-5.4"
    assert payload["input"][0]["content"] == "hi"


def test_gateway_posts_to_responses_api():
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["authorization"] = request.headers["Authorization"]
        captured["body"] = json.loads(request.content.decode("utf-8"))
        return httpx.Response(
            200,
            json={
                "id": "resp_123",
                "output": [
                    {
                        "type": "message",
                        "content": [
                            {
                                "type": "output_text",
                                "text": "hello from gateway",
                            }
                        ],
                    }
                ],
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    gateway = ChatGateway(
        api_key="test-key",
        model="gpt-5.4",
        base_url="http://example.test/v1",
        http_client=client,
    )

    result = gateway.create_response(
        [ChatMessage(role="user", content="hi")],
        instructions="be helpful",
    )

    assert captured["url"] == "http://example.test/v1/responses"
    assert captured["authorization"] == "Bearer test-key"
    assert captured["body"] == {
        "model": "gpt-5.4",
        "input": [{"role": "user", "content": "hi"}],
        "instructions": "be helpful",
    }
    assert result.response_id == "resp_123"
    assert result.output_text == "hello from gateway"
