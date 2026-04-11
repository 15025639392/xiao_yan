import json
import os

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


def test_gateway_responses_create_response_falls_back_to_stream_when_output_missing():
    class StubStreamResponse:
        def raise_for_status(self) -> None:
            return None

        def iter_lines(self):
            return iter(
                [
                    'event: response.created',
                    'data: {"response":{"id":"resp_stream_1"}}',
                    "",
                    'event: response.output_text.delta',
                    'data: {"delta":"hello"}',
                    "",
                    'event: response.output_text.delta',
                    'data: {"delta":" world"}',
                    "",
                    'event: response.completed',
                    'data: {"response":{"id":"resp_stream_1"}}',
                    "",
                ]
            )

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    class StubClient:
        def post(self, url: str, headers: dict, json: dict):
            assert url == "http://example.test/v1/responses"
            request = httpx.Request("POST", url, headers=headers, json=json)
            return httpx.Response(200, json={"id": "resp_empty_1", "output": []}, request=request)

        def stream(self, method: str, url: str, headers: dict, json: dict):
            assert method == "POST"
            assert url == "http://example.test/v1/responses"
            assert json["stream"] is True
            return StubStreamResponse()

        def close(self) -> None:
            return None

    gateway = ChatGateway(
        api_key="test-key",
        model="gpt-5.4",
        base_url="http://example.test/v1",
        wire_api="responses",
        http_client=StubClient(),
    )

    result = gateway.create_response([ChatMessage(role="user", content="hi")])
    assert result.response_id == "resp_stream_1"
    assert result.output_text == "hello world"


def test_gateway_posts_to_chat_completions_api_when_wire_api_chat():
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["body"] = json.loads(request.content.decode("utf-8"))
        return httpx.Response(
            200,
            json={
                "id": "chatcmpl_123",
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "hello from chat gateway",
                        }
                    }
                ],
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    gateway = ChatGateway(
        api_key="test-key",
        model="MiniMax-M2.7",
        base_url="http://example.test/v1",
        wire_api="chat",
        http_client=client,
    )

    result = gateway.create_response(
        [ChatMessage(role="user", content="hi")],
        instructions="be helpful",
    )

    assert captured["url"] == "http://example.test/v1/chat/completions"
    assert captured["body"] == {
        "model": "MiniMax-M2.7",
        "messages": [
            {"role": "system", "content": "be helpful"},
            {"role": "user", "content": "hi"},
        ],
    }
    assert result.response_id == "chatcmpl_123"
    assert result.output_text == "hello from chat gateway"


def test_gateway_chat_create_response_falls_back_to_stream_when_message_content_is_empty():
    class StubStreamResponse:
        def raise_for_status(self) -> None:
            return None

        def iter_lines(self):
            return iter(
                [
                    'data: {"id":"chatcmpl_stream_1","choices":[{"delta":{"role":"assistant"}}]}',
                    "",
                    'data: {"id":"chatcmpl_stream_1","choices":[{"delta":{"content":"hello "}}]}',
                    "",
                    'data: {"id":"chatcmpl_stream_1","choices":[{"delta":{"content":"world"}}]}',
                    "",
                    "data: [DONE]",
                    "",
                ]
            )

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    class StubClient:
        def post(self, url: str, headers: dict, json: dict):
            assert url == "http://example.test/v1/chat/completions"
            request = httpx.Request("POST", url, headers=headers, json=json)
            return httpx.Response(
                200,
                json={
                    "id": "chatcmpl_empty_1",
                    "choices": [
                        {
                            "message": {
                                "role": "assistant",
                                "content": None,
                            }
                        }
                    ],
                },
                request=request,
            )

        def stream(self, method: str, url: str, headers: dict, json: dict):
            assert method == "POST"
            assert url == "http://example.test/v1/chat/completions"
            assert json["stream"] is True
            return StubStreamResponse()

        def close(self) -> None:
            return None

    gateway = ChatGateway(
        api_key="test-key",
        model="gpt-5.4",
        base_url="http://example.test/v1",
        wire_api="chat",
        http_client=StubClient(),
    )

    result = gateway.create_response([ChatMessage(role="user", content="hi")])
    assert result.response_id == "chatcmpl_stream_1"
    assert result.output_text == "hello world"


def test_gateway_streams_chat_completions_events_when_wire_api_chat():
    class StubStreamResponse:
        def raise_for_status(self) -> None:
            return None

        def iter_lines(self):
            return iter(
                [
                    'data: {"id":"chatcmpl_123","choices":[{"delta":{"role":"assistant"}}]}',
                    "",
                    'data: {"id":"chatcmpl_123","choices":[{"delta":{"content":"hello "}}]}',
                    "",
                    'data: {"id":"chatcmpl_123","choices":[{"delta":{"content":"world"}}]}',
                    "",
                    "data: [DONE]",
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
            assert url == "http://example.test/v1/chat/completions"
            assert json["model"] == "MiniMax-M2.7"
            assert json["stream"] is True
            return StubStreamResponse()

    gateway = ChatGateway(
        api_key="test-key",
        model="MiniMax-M2.7",
        base_url="http://example.test/v1",
        wire_api="chat",
        http_client=StubStreamClient(),
    )

    events = list(
        gateway.stream_response(
            [ChatMessage(role="user", content="hi")],
            instructions="be helpful",
        )
    )

    assert events == [
        {"type": "response_started", "response_id": "chatcmpl_123"},
        {"type": "text_delta", "delta": "hello "},
        {"type": "text_delta", "delta": "world"},
        {
            "type": "response_completed",
            "response_id": "chatcmpl_123",
            "output_text": "hello world",
        },
    ]


def test_gateway_chat_wire_normalizes_tool_calls_and_replays_tool_outputs():
    calls: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode("utf-8"))
        calls.append(body)
        if len(calls) == 1:
            return httpx.Response(
                200,
                json={
                    "id": "chatcmpl_tool_1",
                    "choices": [
                        {
                            "message": {
                                "role": "assistant",
                                "content": "",
                                "tool_calls": [
                                    {
                                        "id": "call_1",
                                        "type": "function",
                                        "function": {
                                            "name": "list_directory",
                                            "arguments": '{"path":"/tmp"}',
                                        },
                                    }
                                ],
                            }
                        }
                    ],
                },
            )

        # 第二轮：应包含 assistant(tool_calls) + tool 消息
        messages = body["messages"]
        assert any(msg.get("role") == "assistant" and msg.get("tool_calls") for msg in messages)
        assert any(msg.get("role") == "tool" and msg.get("tool_call_id") == "call_1" for msg in messages)
        return httpx.Response(
            200,
            json={
                "id": "chatcmpl_tool_2",
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "目录内容如下",
                        }
                    }
                ],
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    gateway = ChatGateway(
        api_key="test-key",
        model="MiniMax-M2.7",
        base_url="http://example.test/v1",
        wire_api="chat",
        http_client=client,
    )

    response1 = gateway.create_response_with_tools(
        [{"role": "user", "content": "列目录"}],
        instructions="use tools",
        tools=[
            {
                "type": "function",
                "name": "list_directory",
                "parameters": {"type": "object", "properties": {"path": {"type": "string"}}},
            }
        ],
    )
    assert response1["id"] == "chatcmpl_tool_1"
    assert response1["output"][0]["type"] == "function_call"
    assert response1["output"][0]["call_id"] == "call_1"

    response2 = gateway.create_response_with_tools(
        [
            {"role": "user", "content": "列目录"},
            response1["output"][0],
            {"type": "function_call_output", "call_id": "call_1", "output": '{"entries":["a","b"]}'},
        ],
        instructions="use tools",
        tools=[
            {
                "type": "function",
                "name": "list_directory",
                "parameters": {"type": "object", "properties": {"path": {"type": "string"}}},
            }
        ],
    )
    assert response2["id"] == "chatcmpl_tool_2"
    assert response2["output_text"] == "目录内容如下"


def test_gateway_chat_wire_drops_assistant_text_when_tool_calls_present():
    payload = {
        "id": "chatcmpl_tool_text_1",
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "我先调用工具",
                    "tool_calls": [
                        {
                            "id": "call_1",
                            "type": "function",
                            "function": {
                                "name": "list_directory",
                                "arguments": '{"path":"/tmp"}',
                            },
                        }
                    ],
                }
            }
        ],
    }

    normalized = ChatGateway._normalize_chat_completion_response(payload)
    assert normalized["id"] == "chatcmpl_tool_text_1"
    assert normalized["output_text"] == ""
    assert normalized["output"] == [
        {
            "type": "function_call",
            "call_id": "call_1",
            "name": "list_directory",
            "arguments": '{"path":"/tmp"}',
        }
    ]


def test_gateway_from_env_supports_minimax_key_and_chat_default():
    env_backup = {
        "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY"),
        "MINIMAX_API_KEY": os.getenv("MINIMAX_API_KEY"),
        "MINIMAX_MODEL": os.getenv("MINIMAX_MODEL"),
        "OPENAI_BASE_URL": os.getenv("OPENAI_BASE_URL"),
        "OPENAI_WIRE_API": os.getenv("OPENAI_WIRE_API"),
        "OPENAI_MODEL": os.getenv("OPENAI_MODEL"),
        "NVIDIA_API_KEY": os.getenv("NVIDIA_API_KEY"),
        "CHAT_PROVIDER": os.getenv("CHAT_PROVIDER"),
    }

    try:
        os.environ["OPENAI_API_KEY"] = ""
        os.environ["MINIMAX_API_KEY"] = "minimax-key"
        os.environ["MINIMAX_MODEL"] = "MiniMax-M2.7"
        os.environ["OPENAI_BASE_URL"] = "https://api.minimaxi.com/v1"
        os.environ.pop("OPENAI_WIRE_API", None)
        os.environ["OPENAI_MODEL"] = "MiniMax-M2.7"
        os.environ["NVIDIA_API_KEY"] = ""
        # Keep an explicit empty value so load_local_env() does not re-inject
        # CHAT_PROVIDER from local .env files via os.environ.setdefault().
        os.environ["CHAT_PROVIDER"] = ""

        gateway = ChatGateway.from_env()
        assert gateway.api_key == "minimax-key"
        assert gateway.wire_api == "chat"
        assert gateway.model == "MiniMax-M2.7"
    finally:
        for key, value in env_backup.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def test_gateway_from_env_supports_nvidia_key_and_chat_default():
    env_backup = {
        "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY"),
        "MINIMAX_API_KEY": os.getenv("MINIMAX_API_KEY"),
        "NVIDIA_API_KEY": os.getenv("NVIDIA_API_KEY"),
        "NVIDIA_MODEL": os.getenv("NVIDIA_MODEL"),
        "NVIDIA_BASE_URL": os.getenv("NVIDIA_BASE_URL"),
        "NVIDIA_WIRE_API": os.getenv("NVIDIA_WIRE_API"),
        "CHAT_PROVIDER": os.getenv("CHAT_PROVIDER"),
    }

    try:
        os.environ["OPENAI_API_KEY"] = ""
        os.environ["MINIMAX_API_KEY"] = ""
        os.environ["NVIDIA_API_KEY"] = "nvidia-key"
        os.environ["NVIDIA_MODEL"] = "meta/llama-3.1-70b-instruct"
        os.environ["NVIDIA_BASE_URL"] = "https://integrate.api.nvidia.com/v1"
        os.environ.pop("NVIDIA_WIRE_API", None)
        os.environ["CHAT_PROVIDER"] = "nvidia"

        gateway = ChatGateway.from_env()
        assert gateway.api_key == "nvidia-key"
        assert gateway.wire_api == "chat"
        assert gateway.model == "meta/llama-3.1-70b-instruct"
        assert gateway.base_url == "https://integrate.api.nvidia.com/v1"
    finally:
        for key, value in env_backup.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def test_gateway_from_env_supports_deepseek_key_and_chat_default():
    env_backup = {
        "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY"),
        "MINIMAX_API_KEY": os.getenv("MINIMAX_API_KEY"),
        "NVIDIA_API_KEY": os.getenv("NVIDIA_API_KEY"),
        "DEEPSEEK_API_KEY": os.getenv("DEEPSEEK_API_KEY"),
        "DEEPSEEK_MODEL": os.getenv("DEEPSEEK_MODEL"),
        "DEEPSEEK_BASE_URL": os.getenv("DEEPSEEK_BASE_URL"),
        "DEEPSEEK_WIRE_API": os.getenv("DEEPSEEK_WIRE_API"),
        "CHAT_PROVIDER": os.getenv("CHAT_PROVIDER"),
    }

    try:
        os.environ["OPENAI_API_KEY"] = ""
        os.environ["MINIMAX_API_KEY"] = ""
        os.environ["NVIDIA_API_KEY"] = ""
        os.environ["DEEPSEEK_API_KEY"] = "deepseek-key"
        os.environ["DEEPSEEK_MODEL"] = "deepseek-chat"
        os.environ["DEEPSEEK_BASE_URL"] = "https://api.deepseek.com"
        os.environ.pop("DEEPSEEK_WIRE_API", None)
        os.environ["CHAT_PROVIDER"] = "deepseek"

        gateway = ChatGateway.from_env()
        assert gateway.api_key == "deepseek-key"
        assert gateway.wire_api == "chat"
        assert gateway.model == "deepseek-chat"
        assert gateway.base_url == "https://api.deepseek.com"
    finally:
        for key, value in env_backup.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def test_gateway_chat_wire_merges_multiple_system_messages():
    gateway = ChatGateway(
        api_key="test-key",
        model="MiniMax-M2.7",
        base_url="http://example.test/v1",
        wire_api="chat",
    )

    payload_messages = gateway._build_chat_messages(
        [
            ChatMessage(role="system", content="memory A"),
            ChatMessage(role="assistant", content="prev answer"),
            ChatMessage(role="system", content="memory B"),
            ChatMessage(role="user", content="new question"),
        ],
        instructions="main instruction",
    )

    assert payload_messages[0]["role"] == "system"
    assert payload_messages[0]["content"] == "main instruction\n\nmemory A\n\nmemory B"
    assert payload_messages[1:] == [
        {"role": "assistant", "content": "prev answer"},
        {"role": "user", "content": "new question"},
    ]


def test_gateway_chat_wire_merges_system_messages_in_tool_loop_input():
    gateway = ChatGateway(
        api_key="test-key",
        model="MiniMax-M2.7",
        base_url="http://example.test/v1",
        wire_api="chat",
    )

    messages = gateway._convert_input_items_to_chat_messages(
        [
            {"role": "system", "content": "memory A"},
            {"role": "assistant", "content": "prev answer"},
            {"role": "system", "content": "memory B"},
            {"role": "user", "content": "new question"},
        ],
        instructions="main instruction",
    )

    assert messages[0]["role"] == "system"
    assert messages[0]["content"] == "main instruction\n\nmemory A\n\nmemory B"
    assert messages[1:] == [
        {"role": "assistant", "content": "prev answer"},
        {"role": "user", "content": "new question"},
    ]
