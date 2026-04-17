from __future__ import annotations

import httpx
from fastapi import HTTPException, Request

from app.api.chat_runtime_helpers import (
    merge_chat_stream_content,
    should_fallback_to_stream_without_tools,
)
from app.api.chat_tool_calls import (
    build_function_call_signature,
    execute_tool_call,
    extract_function_calls,
    extract_output_text,
)
from app.api.file_tool_helpers import build_file_tools, file_policy_args
from app.llm.gateway import ChatGateway
from app.llm.schemas import ChatMessage, ChatReasoningState, ChatSubmissionResult
from app.mcp import ChatMcpCallRegistry

CHAT_FILE_TOOL_DEFINITIONS = [
    {
        "type": "function",
        "name": "read_file",
        "description": "Read a file and return its content. Use absolute paths when possible.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "max_bytes": {"type": "integer", "minimum": 1, "maximum": 2 * 1024 * 1024},
            },
            "required": ["path"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "list_directory",
        "description": "List files and directories under a path.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "recursive": {"type": "boolean"},
                "pattern": {"type": "string"},
            },
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "search_files",
        "description": "Search text in files under a path.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "search_path": {"type": "string"},
                "file_pattern": {"type": "string"},
                "max_results": {"type": "integer", "minimum": 1, "maximum": 200},
            },
            "required": ["query"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "write_file",
        "description": "Write UTF-8 text to a file path. Requires full_access for granted folders.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"},
                "create_dirs": {"type": "boolean"},
            },
            "required": ["path", "content"],
            "additionalProperties": False,
        },
    },
]


def build_resume_instruction(partial_content: str) -> str:
    return (
        "这是一次失败后的继续生成。"
        "你必须紧接着下面这段 assistant 已输出内容继续生成，"
        "不要重复已经说过的文字，不要重开话题，不要改写前文。\n\n"
        f"已输出内容：\n{partial_content}"
    )


def run_chat_submission(
    *,
    request: Request,
    gateway: ChatGateway,
    chat_messages: list[ChatMessage],
    instructions: str,
    assistant_message_id: str,
    initial_output_text: str = "",
    suppress_started_event: bool = False,
    knowledge_references: list[dict[str, str | float | None]] | None = None,
    request_key: str | None = None,
    reasoning_session_id: str | None = None,
    reasoning_state: ChatReasoningState | None = None,
) -> tuple[ChatSubmissionResult, str]:
    response_id: str | None = None
    output_text = initial_output_text
    started = False
    hub = getattr(request.app.state, "realtime_hub", None)
    reasoning_payload = reasoning_state.model_dump(mode="json") if reasoning_state is not None else None

    try:
        for event in gateway.stream_response(chat_messages, instructions=instructions):
            event_type = event["type"]
            if event_type == "response_started":
                response_id = event.get("response_id") or response_id
                if hub is not None and not started and not suppress_started_event:
                    hub.publish_chat_started(
                        assistant_message_id,
                        response_id=response_id,
                        request_key=request_key,
                        reasoning_session_id=reasoning_session_id,
                        reasoning_state=reasoning_payload,
                    )
                    started = True
                continue

            if event_type == "text_delta":
                if hub is not None and not started and not suppress_started_event:
                    hub.publish_chat_started(
                        assistant_message_id,
                        response_id=response_id,
                        request_key=request_key,
                        reasoning_session_id=reasoning_session_id,
                        reasoning_state=reasoning_payload,
                    )
                    started = True

                delta = event.get("delta") or ""
                if not delta:
                    continue

                output_text = merge_chat_stream_content(output_text, delta)
                if hub is not None:
                    hub.publish_chat_delta(
                        assistant_message_id,
                        delta,
                        request_key=request_key,
                        reasoning_session_id=reasoning_session_id,
                        reasoning_state=reasoning_payload,
                    )
                continue

            if event_type == "response_completed":
                response_id = event.get("response_id") or response_id
                completed_output_text = event.get("output_text") or ""
                if completed_output_text and completed_output_text not in output_text:
                    output_text = completed_output_text
                continue

            if event_type == "response_failed":
                error_message = event.get("error") or "streaming failed"
                if hub is not None:
                    hub.publish_chat_failed(
                        assistant_message_id,
                        error_message,
                        request_key=request_key,
                        reasoning_session_id=reasoning_session_id,
                        reasoning_state=reasoning_payload,
                    )
                raise HTTPException(status_code=502, detail=error_message)
    except httpx.HTTPStatusError as exception:
        detail = str(exception)
        try:
            if exception.response is not None:
                detail = exception.response.text or detail
        except Exception:  # noqa: BLE001
            pass
        if hub is not None:
            hub.publish_chat_failed(
                assistant_message_id,
                detail,
                request_key=request_key,
                reasoning_session_id=reasoning_session_id,
                reasoning_state=reasoning_payload,
            )
        raise HTTPException(status_code=502, detail=detail) from exception
    except HTTPException:
        raise
    except Exception as exception:
        if hub is not None:
            hub.publish_chat_failed(
                assistant_message_id,
                str(exception),
                request_key=request_key,
                reasoning_session_id=reasoning_session_id,
                reasoning_state=reasoning_payload,
            )
        raise HTTPException(status_code=502, detail=str(exception)) from exception

    if hub is not None and not started and not suppress_started_event:
        hub.publish_chat_started(
            assistant_message_id,
            response_id=response_id,
            request_key=request_key,
            reasoning_session_id=reasoning_session_id,
            reasoning_state=reasoning_payload,
        )
    if hub is not None:
        hub.publish_chat_completed(
            assistant_message_id,
            response_id,
            output_text,
            request_key=request_key,
            knowledge_references=knowledge_references,
            reasoning_session_id=reasoning_session_id,
            reasoning_state=reasoning_payload,
        )

    return (
        ChatSubmissionResult(
            response_id=response_id,
            assistant_message_id=assistant_message_id,
            request_key=request_key,
        ),
        output_text,
    )


def run_chat_submission_with_tools(
    *,
    request: Request,
    gateway: ChatGateway,
    chat_messages: list[ChatMessage],
    instructions: str,
    assistant_message_id: str,
    initial_output_text: str = "",
    knowledge_references: list[dict[str, str | float | None]] | None = None,
    extra_tools: list[dict[str, object]] | None = None,
    mcp_registry: ChatMcpCallRegistry | None = None,
    request_key: str | None = None,
    reasoning_session_id: str | None = None,
    reasoning_state: ChatReasoningState | None = None,
) -> tuple[ChatSubmissionResult, str]:
    create_with_tools = getattr(gateway, "create_response_with_tools", None)
    if not callable(create_with_tools):
        return run_chat_submission(
            request=request,
            gateway=gateway,
            chat_messages=chat_messages,
            instructions=instructions,
            assistant_message_id=assistant_message_id,
            initial_output_text=initial_output_text,
            knowledge_references=knowledge_references,
            request_key=request_key,
            reasoning_session_id=reasoning_session_id,
            reasoning_state=reasoning_state,
        )

    hub = getattr(request.app.state, "realtime_hub", None)
    started = False
    response_id: str | None = None
    reasoning_payload = reasoning_state.model_dump(mode="json") if reasoning_state is not None else None

    file_tools = build_file_tools()
    tool_definitions = [*CHAT_FILE_TOOL_DEFINITIONS, *(extra_tools or [])]
    accumulated_input: list[dict] = [message.model_dump() for message in chat_messages]
    max_tool_rounds = 8
    tool_repeat_streak_limit = 3
    last_call_signature: str | None = None
    same_call_signature_streak = 0
    payload_hint = f"messages={len(chat_messages)}, instructions_chars={len(instructions or '')}"

    def _fallback_without_tools(reason: str) -> tuple[ChatSubmissionResult, str]:
        fallback_instructions = (
            f"{instructions}\n\n"
            "[Tool fallback]\n"
            f"工具调用出现循环/超限（{reason}）。"
            "请不要再调用任何工具，直接基于已有上下文回答；"
            "如信息不足请明确说明不足点。"
        )
        return run_chat_submission(
            request=request,
            gateway=gateway,
            chat_messages=chat_messages,
            instructions=fallback_instructions,
            assistant_message_id=assistant_message_id,
            initial_output_text=initial_output_text,
            suppress_started_event=started,
            knowledge_references=knowledge_references,
            reasoning_session_id=reasoning_session_id,
            reasoning_state=reasoning_state,
        )

    try:
        for _ in range(max_tool_rounds):
            try:
                response_payload = create_with_tools(
                    accumulated_input,
                    instructions=instructions,
                    tools=tool_definitions,
                )
            except Exception as exception:  # noqa: BLE001
                if (
                    not started
                    and len(accumulated_input) == len(chat_messages)
                    and should_fallback_to_stream_without_tools(exception)
                ):
                    return run_chat_submission(
                        request=request,
                        gateway=gateway,
                        chat_messages=chat_messages,
                        instructions=instructions,
                        assistant_message_id=assistant_message_id,
                        initial_output_text=initial_output_text,
                        knowledge_references=knowledge_references,
                        request_key=request_key,
                        reasoning_session_id=reasoning_session_id,
                        reasoning_state=reasoning_state,
                    )
                raise
            if not isinstance(response_payload, dict):
                raise HTTPException(status_code=502, detail="invalid gateway response payload")

            current_response_id = response_payload.get("id")
            if isinstance(current_response_id, str):
                response_id = current_response_id

            function_calls = extract_function_calls(response_payload)
            if not function_calls:
                output_text = extract_output_text(response_payload)
                if initial_output_text:
                    output_text = merge_chat_stream_content(initial_output_text, output_text)

                if not output_text and not started and len(accumulated_input) == len(chat_messages):
                    return run_chat_submission(
                        request=request,
                        gateway=gateway,
                        chat_messages=chat_messages,
                        instructions=instructions,
                        assistant_message_id=assistant_message_id,
                        initial_output_text=initial_output_text,
                        knowledge_references=knowledge_references,
                        request_key=request_key,
                        reasoning_session_id=reasoning_session_id,
                        reasoning_state=reasoning_state,
                    )

                if not output_text:
                    raise HTTPException(status_code=502, detail="empty gateway response payload")

                if hub is not None and not started:
                    hub.publish_chat_started(
                        assistant_message_id,
                        response_id=response_id,
                        request_key=request_key,
                        reasoning_session_id=reasoning_session_id,
                        reasoning_state=reasoning_payload,
                    )
                    started = True

                if hub is not None and output_text:
                    hub.publish_chat_delta(
                        assistant_message_id,
                        output_text,
                        request_key=request_key,
                        reasoning_session_id=reasoning_session_id,
                        reasoning_state=reasoning_payload,
                    )
                if hub is not None:
                    hub.publish_chat_completed(
                        assistant_message_id,
                        response_id,
                        output_text,
                        request_key=request_key,
                        knowledge_references=knowledge_references,
                        reasoning_session_id=reasoning_session_id,
                        reasoning_state=reasoning_payload,
                    )

                return (
                    ChatSubmissionResult(
                        response_id=response_id,
                        assistant_message_id=assistant_message_id,
                        request_key=request_key,
                    ),
                    output_text,
                )

            if hub is not None and not started:
                hub.publish_chat_started(
                    assistant_message_id,
                    response_id=response_id,
                    request_key=request_key,
                    reasoning_session_id=reasoning_session_id,
                    reasoning_state=reasoning_payload,
                )
                started = True

            call_signature = build_function_call_signature(function_calls)
            if call_signature == last_call_signature:
                same_call_signature_streak += 1
            else:
                same_call_signature_streak = 1
                last_call_signature = call_signature
            if same_call_signature_streak >= tool_repeat_streak_limit:
                return _fallback_without_tools("repeated_tool_calls")

            tool_outputs: list[dict[str, str]] = []
            for call_id, tool_name, arguments in function_calls:
                tool_output = execute_tool_call(
                    file_tools,
                    tool_name,
                    arguments,
                    file_policy_args=file_policy_args(),
                    mcp_registry=mcp_registry,
                )
                tool_outputs.append(
                    {
                        "type": "function_call_output",
                        "call_id": call_id,
                        "output": tool_output,
                    }
                )

            response_outputs = response_payload.get("output", [])
            if isinstance(response_outputs, list):
                for output_item in response_outputs:
                    if isinstance(output_item, dict):
                        accumulated_input.append(output_item)

            accumulated_input.extend(tool_outputs)

        return _fallback_without_tools("tool_call_recursion_limit_exceeded")
    except HTTPException:
        if hub is not None and started:
            hub.publish_chat_failed(
                assistant_message_id,
                "tool execution failed",
                request_key=request_key,
                reasoning_session_id=reasoning_session_id,
                reasoning_state=reasoning_payload,
            )
        raise
    except httpx.HTTPStatusError as exception:
        detail = str(exception)
        try:
            if exception.response is not None:
                detail = exception.response.text or detail
        except Exception:  # noqa: BLE001
            pass
        if hub is not None and started:
            hub.publish_chat_failed(
                assistant_message_id,
                f"{payload_hint}; {detail}",
                request_key=request_key,
                reasoning_session_id=reasoning_session_id,
                reasoning_state=reasoning_payload,
            )
        raise HTTPException(status_code=502, detail=f"{payload_hint}; {detail}") from exception
    except Exception as exception:  # noqa: BLE001
        if hub is not None and started:
            hub.publish_chat_failed(
                assistant_message_id,
                str(exception),
                request_key=request_key,
                reasoning_session_id=reasoning_session_id,
                reasoning_state=reasoning_payload,
            )
        raise HTTPException(status_code=502, detail=str(exception)) from exception
