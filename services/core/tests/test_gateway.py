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


def test_gateway_streams_responses_api_events():
    class StubStreamResponse:
        def raise_for_status(self) -> None:
            return None

        def iter_lines(self):
            return iter(
                [
                    'event: response.created',
                    'data: {"response":{"id":"resp_123"}}',
                    "",
                    'event: response.output_text.delta',
                    'data: {"delta":"hello "}',
                    "",
                    'event: response.output_text.delta',
                    'data: {"delta":"world"}',
                    "",
                    'event: response.completed',
                    'data: {"response":{"id":"resp_123"}}',
                    "",
                ]
            )

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    class StubStreamClient:
        def stream(self, method: str, url: str, headers: dict, json: dict):
            assert method == "POST"
            assert url == "http://example.test/v1/responses"
            assert headers["Authorization"] == "Bearer test-key"
            assert json["input"] == [{"role": "user", "content": "hi"}]
            return StubStreamResponse()

    gateway = ChatGateway(
        api_key="test-key",
        model="gpt-5.4",
        base_url="http://example.test/v1",
        http_client=StubStreamClient(),
    )

    events = list(
        gateway.stream_response(
            [ChatMessage(role="user", content="hi")],
            instructions="be helpful",
        )
    )

    assert events == [
        {"type": "response_started", "response_id": "resp_123"},
        {"type": "text_delta", "delta": "hello "},
        {"type": "text_delta", "delta": "world"},
        {
            "type": "response_completed",
            "response_id": "resp_123",
            "output_text": "hello world",
        },
    ]
