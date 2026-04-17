from types import SimpleNamespace

import httpx

from app.api import chat_submission_runner
from app.api.chat_submission_runner import run_chat_submission_with_tools
from app.llm.schemas import ChatMessage, ChatReasoningState


class RecordingHub:
    def __init__(self) -> None:
        self.started: list[dict] = []
        self.deltas: list[dict] = []
        self.completed: list[dict] = []
        self.failed: list[dict] = []

    def publish_chat_started(self, assistant_message_id: str, **kwargs) -> None:
        self.started.append({"assistant_message_id": assistant_message_id, **kwargs})

    def publish_chat_delta(self, assistant_message_id: str, delta: str, **kwargs) -> None:
        self.deltas.append({"assistant_message_id": assistant_message_id, "delta": delta, **kwargs})

    def publish_chat_completed(
        self,
        assistant_message_id: str,
        response_id: str | None,
        content: str,
        **kwargs,
    ) -> None:
        self.completed.append(
            {
                "assistant_message_id": assistant_message_id,
                "response_id": response_id,
                "content": content,
                **kwargs,
            }
        )

    def publish_chat_failed(self, assistant_message_id: str, error: str, **kwargs) -> None:
        self.failed.append({"assistant_message_id": assistant_message_id, "error": error, **kwargs})


class MixedAssistantTextToolGateway:
    def __init__(self) -> None:
        self.create_calls: list[list[dict]] = []

    def create_response_with_tools(
        self,
        input_items,
        *,
        instructions=None,
        tools=None,
        previous_response_id=None,
    ):
        _ = (instructions, tools, previous_response_id)
        self.create_calls.append(list(input_items))
        if len(self.create_calls) == 1:
            return {
                "id": "resp_tool_mixed_1",
                "output": [
                    {
                        "type": "message",
                        "role": "assistant",
                        "content": [
                            {
                                "type": "output_text",
                                "text": "我先看一下文件。",
                            }
                        ],
                    },
                    {
                        "type": "function_call",
                        "call_id": "call_1",
                        "name": "read_file",
                        "arguments": '{"path":"/tmp/demo.txt"}',
                    },
                ],
            }

        replayed_items = self.create_calls[-1]
        assert any(
            isinstance(item, dict)
            and item.get("type") == "message"
            and item.get("content", [{}])[0].get("text") == "我先看一下文件。"
            for item in replayed_items
        )
        assert any(
            isinstance(item, dict)
            and item.get("type") == "function_call_output"
            and item.get("call_id") == "call_1"
            and item.get("output") == '{"ok":true}'
            for item in replayed_items
        )
        return {
            "id": "resp_tool_mixed_2",
            "output": [
                {
                    "type": "message",
                    "role": "assistant",
                    "content": [
                        {
                            "type": "output_text",
                            "text": "已经拿到结果。",
                        }
                    ],
                }
            ],
            "output_text": "已经拿到结果。",
        }


class ToolFallbackResumeGateway:
    def create_response_with_tools(
        self,
        input_items,
        *,
        instructions=None,
        tools=None,
        previous_response_id=None,
    ):
        _ = (input_items, instructions, tools, previous_response_id)
        request = httpx.Request("POST", "https://api.example.test/v1/chat/completions")
        response = httpx.Response(400, request=request, json={"error": {"message": "tools not supported"}})
        raise httpx.HTTPStatusError("Bad Request", request=request, response=response)

    def stream_response(self, messages, instructions=None):
        _ = (messages, instructions)
        yield {
            "type": "response_started",
            "response_id": "resp_resume_fallback",
        }
        yield {
            "type": "text_delta",
            "delta": "继续补完",
        }
        yield {
            "type": "response_completed",
            "response_id": "resp_resume_fallback",
            "output_text": "继续补完",
        }


class ResponsesTextContentToolGateway:
    def create_response_with_tools(
        self,
        input_items,
        *,
        instructions=None,
        tools=None,
        previous_response_id=None,
    ):
        _ = (input_items, instructions, tools, previous_response_id)
        return {
            "id": "resp_text_content_1",
            "output": [
                {
                    "type": "message",
                    "role": "assistant",
                    "content": [
                        {"type": "text", "text": "第一段。"},
                    ],
                },
                {
                    "type": "reasoning",
                    "summary": [{"type": "summary_text", "text": "忽略"}],
                },
                {
                    "type": "message",
                    "role": "assistant",
                    "content": [
                        {"type": "text", "text": "第二段。"},
                    ],
                },
            ],
        }


class RotatingCallIdLoopGateway:
    def __init__(self) -> None:
        self.create_call_count = 0
        self.stream_call_count = 0

    def create_response_with_tools(
        self,
        input_items,
        *,
        instructions=None,
        tools=None,
        previous_response_id=None,
    ):
        _ = (input_items, instructions, tools, previous_response_id)
        self.create_call_count += 1
        return {
            "id": f"resp_loop_{self.create_call_count}",
            "output": [
                {
                    "type": "function_call",
                    "call_id": f"call_{self.create_call_count}",
                    "name": "search_files",
                    "arguments": '{"query":"same"}',
                }
            ],
        }

    def stream_response(self, messages, instructions=None):
        _ = (messages, instructions)
        self.stream_call_count += 1
        yield {
            "type": "response_started",
            "response_id": "resp_loop_fallback",
        }
        yield {
            "type": "text_delta",
            "delta": "停止循环后直接回答。",
        }
        yield {
            "type": "response_completed",
            "response_id": "resp_loop_fallback",
            "output_text": "停止循环后直接回答。",
        }


class ReorderedMultiToolLoopGateway:
    def __init__(self) -> None:
        self.create_call_count = 0
        self.stream_call_count = 0

    def create_response_with_tools(
        self,
        input_items,
        *,
        instructions=None,
        tools=None,
        previous_response_id=None,
    ):
        _ = (input_items, instructions, tools, previous_response_id)
        self.create_call_count += 1
        if self.create_call_count % 2 == 1:
            output = [
                {
                    "type": "function_call",
                    "call_id": f"call_a_{self.create_call_count}",
                    "name": "search_files",
                    "arguments": '{"query":"same","search_path":"/tmp"}',
                },
                {
                    "type": "function_call",
                    "call_id": f"call_b_{self.create_call_count}",
                    "name": "list_directory",
                    "arguments": '{"path":"/tmp","recursive":false}',
                },
            ]
        else:
            output = [
                {
                    "type": "function_call",
                    "call_id": f"call_b_{self.create_call_count}",
                    "name": "list_directory",
                    "arguments": '{"recursive":false,"path":"/tmp"}',
                },
                {
                    "type": "function_call",
                    "call_id": f"call_a_{self.create_call_count}",
                    "name": "search_files",
                    "arguments": '{"search_path":"/tmp","query":"same"}',
                },
            ]
        return {
            "id": f"resp_multi_loop_{self.create_call_count}",
            "output": output,
        }

    def stream_response(self, messages, instructions=None):
        _ = (messages, instructions)
        self.stream_call_count += 1
        yield {
            "type": "response_started",
            "response_id": "resp_multi_loop_fallback",
        }
        yield {
            "type": "text_delta",
            "delta": "检测到重复工具集合后直接回答。",
        }
        yield {
            "type": "response_completed",
            "response_id": "resp_multi_loop_fallback",
            "output_text": "检测到重复工具集合后直接回答。",
        }


def test_run_chat_submission_with_tools_replays_mixed_assistant_text_before_tool_output(monkeypatch):
    monkeypatch.setattr(chat_submission_runner, "execute_tool_call", lambda *args, **kwargs: '{"ok":true}')
    gateway = MixedAssistantTextToolGateway()
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(realtime_hub=None)))

    result, output_text = run_chat_submission_with_tools(
        request=request,
        gateway=gateway,
        chat_messages=[ChatMessage(role="user", content="读一下文件")],
        instructions="你可以用工具",
        assistant_message_id="assistant_tool_mixed_1",
    )

    assert result.response_id == "resp_tool_mixed_2"
    assert result.assistant_message_id == "assistant_tool_mixed_1"
    assert output_text == "已经拿到结果。"
    assert len(gateway.create_calls) == 2


def test_run_chat_submission_with_tools_resume_fallback_keeps_request_key_and_reasoning_in_events():
    gateway = ToolFallbackResumeGateway()
    hub = RecordingHub()
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(realtime_hub=hub)))
    reasoning_state = ChatReasoningState(
        session_id="reasoning_resume_1",
        phase="exploring",
        step_index=3,
        summary="继续追踪 fallback",
        updated_at="2026-04-18T08:00:00+00:00",
    )

    result, output_text = run_chat_submission_with_tools(
        request=request,
        gateway=gateway,
        chat_messages=[ChatMessage(role="user", content="继续")],
        instructions="继续回答",
        assistant_message_id="assistant_resume_1",
        initial_output_text="前半句，",
        request_key="request_resume_1",
        reasoning_session_id=reasoning_state.session_id,
        reasoning_state=reasoning_state,
    )

    assert result.response_id == "resp_resume_fallback"
    assert result.request_key == "request_resume_1"
    assert output_text == "前半句，继续补完"

    assert len(hub.started) == 1
    assert len(hub.deltas) == 1
    assert len(hub.completed) == 1
    assert not hub.failed

    assert hub.started[0]["request_key"] == "request_resume_1"
    assert hub.started[0]["reasoning_session_id"] == "reasoning_resume_1"
    assert hub.started[0]["reasoning_state"]["step_index"] == 3

    assert hub.deltas[0]["request_key"] == "request_resume_1"
    assert hub.deltas[0]["reasoning_session_id"] == "reasoning_resume_1"
    assert hub.deltas[0]["delta"] == "继续补完"

    assert hub.completed[0]["request_key"] == "request_resume_1"
    assert hub.completed[0]["reasoning_session_id"] == "reasoning_resume_1"
    assert hub.completed[0]["content"] == "前半句，继续补完"


def test_run_chat_submission_with_tools_accepts_text_content_items_in_final_response():
    gateway = ResponsesTextContentToolGateway()
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(realtime_hub=None)))

    result, output_text = run_chat_submission_with_tools(
        request=request,
        gateway=gateway,
        chat_messages=[ChatMessage(role="user", content="给我结论")],
        instructions="直接回答",
        assistant_message_id="assistant_text_content_1",
    )

    assert result.response_id == "resp_text_content_1"
    assert output_text == "第一段。第二段。"


def test_run_chat_submission_with_tools_detects_repeated_calls_even_when_call_ids_change():
    gateway = RotatingCallIdLoopGateway()
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(realtime_hub=None)))

    result, output_text = run_chat_submission_with_tools(
        request=request,
        gateway=gateway,
        chat_messages=[ChatMessage(role="user", content="继续试")],
        instructions="能用工具就用工具",
        assistant_message_id="assistant_loop_1",
    )

    assert result.response_id == "resp_loop_fallback"
    assert output_text == "停止循环后直接回答。"
    assert gateway.stream_call_count == 1
    assert gateway.create_call_count == 3


def test_run_chat_submission_with_tools_detects_repeated_multi_calls_even_when_order_changes():
    gateway = ReorderedMultiToolLoopGateway()
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(realtime_hub=None)))

    result, output_text = run_chat_submission_with_tools(
        request=request,
        gateway=gateway,
        chat_messages=[ChatMessage(role="user", content="继续试")],
        instructions="能用工具就用工具",
        assistant_message_id="assistant_multi_loop_1",
    )

    assert result.response_id == "resp_multi_loop_fallback"
    assert output_text == "检测到重复工具集合后直接回答。"
    assert gateway.stream_call_count == 1
    assert gateway.create_call_count == 3
