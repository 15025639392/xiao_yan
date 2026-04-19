from __future__ import annotations

import httpx
from fastapi import HTTPException, Request

from app.api.chat_submission_events import ChatSubmissionEvents
from app.api.chat_runtime_helpers import (
    merge_chat_stream_content,
    should_fallback_to_stream_without_tools,
)
from app.api.chat_submission_payloads import (
    CHAT_FILE_TOOL_DEFINITIONS,
    build_resume_instruction,
    resolve_completed_output_text,
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

def run_chat_submission(
    *,
    request: Request,
    gateway: ChatGateway,
    chat_messages: list[ChatMessage],
    instructions: str,
    assistant_message_id: str,
    initial_output_text: str = "",
    suppress_started_event: bool = False,
    memory_references: list[dict[str, str | float | None]] | None = None,
    request_key: str | None = None,
    reasoning_session_id: str | None = None,
    reasoning_state: ChatReasoningState | None = None,
) -> tuple[ChatSubmissionResult, str]:
    response_id: str | None = None
    output_text = initial_output_text
    hub = getattr(request.app.state, "realtime_hub", None)
    reasoning_payload = reasoning_state.model_dump(mode="json") if reasoning_state is not None else None
    events = ChatSubmissionEvents(
        hub=hub,
        assistant_message_id=assistant_message_id,
        request_key=request_key,
        reasoning_session_id=reasoning_session_id,
        reasoning_payload=reasoning_payload,
        suppress_started_event=suppress_started_event,
    )

    try:
        for event in gateway.stream_response(chat_messages, instructions=instructions):
            event_type = event["type"]
            if event_type == "response_started":
                response_id = event.get("response_id") or response_id
                events.publish_started(response_id)
                continue

            if event_type == "text_delta":
                delta = event.get("delta") or ""
                output_text = merge_chat_stream_content(output_text, delta)
                events.publish_delta(delta, response_id=response_id)
                continue

            if event_type == "response_completed":
                response_id = event.get("response_id") or response_id
                completed_output_text = event.get("output_text") or ""
                output_text = resolve_completed_output_text(
                    current_output_text=output_text,
                    completed_output_text=completed_output_text,
                    initial_output_text=initial_output_text,
                )
                continue

            if event_type == "response_failed":
                error_message = event.get("error") or "streaming failed"
                events.publish_failed(error_message)
                raise HTTPException(status_code=502, detail=error_message)
    except httpx.HTTPStatusError as exception:
        detail = str(exception)
        try:
            if exception.response is not None:
                detail = exception.response.text or detail
        except Exception:  # noqa: BLE001
            pass
        events.publish_failed(detail)
        raise HTTPException(status_code=502, detail=detail) from exception
    except HTTPException:
        raise
    except Exception as exception:
        events.publish_failed(str(exception))
        raise HTTPException(status_code=502, detail=str(exception)) from exception

    events.publish_completed(
        response_id=response_id,
        output_text=output_text,
        memory_references=memory_references,
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
    memory_references: list[dict[str, str | float | None]] | None = None,
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
            memory_references=memory_references,
            request_key=request_key,
            reasoning_session_id=reasoning_session_id,
            reasoning_state=reasoning_state,
        )

    hub = getattr(request.app.state, "realtime_hub", None)
    response_id: str | None = None
    reasoning_payload = reasoning_state.model_dump(mode="json") if reasoning_state is not None else None
    events = ChatSubmissionEvents(
        hub=hub,
        assistant_message_id=assistant_message_id,
        request_key=request_key,
        reasoning_session_id=reasoning_session_id,
        reasoning_payload=reasoning_payload,
    )

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
            suppress_started_event=events.started,
            memory_references=memory_references,
            request_key=request_key,
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
                    not events.started
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
                        memory_references=memory_references,
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

                if not output_text and not events.started and len(accumulated_input) == len(chat_messages):
                    return run_chat_submission(
                        request=request,
                        gateway=gateway,
                        chat_messages=chat_messages,
                        instructions=instructions,
                        assistant_message_id=assistant_message_id,
                        initial_output_text=initial_output_text,
                        memory_references=memory_references,
                        request_key=request_key,
                        reasoning_session_id=reasoning_session_id,
                        reasoning_state=reasoning_state,
                    )

                if not output_text:
                    raise HTTPException(status_code=502, detail="empty gateway response payload")

                events.publish_delta(output_text, response_id=response_id)
                events.publish_completed(
                    response_id=response_id,
                    output_text=output_text,
                    memory_references=memory_references,
                )

                return (
                    ChatSubmissionResult(
                        response_id=response_id,
                        assistant_message_id=assistant_message_id,
                        request_key=request_key,
                    ),
                    output_text,
                )

            events.publish_started(response_id)

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
        events.publish_failed("tool execution failed", only_if_started=True)
        raise
    except httpx.HTTPStatusError as exception:
        detail = str(exception)
        try:
            if exception.response is not None:
                detail = exception.response.text or detail
        except Exception:  # noqa: BLE001
            pass
        events.publish_failed(f"{payload_hint}; {detail}", only_if_started=True)
        raise HTTPException(status_code=502, detail=f"{payload_hint}; {detail}") from exception
    except Exception as exception:  # noqa: BLE001
        events.publish_failed(str(exception), only_if_started=True)
        raise HTTPException(status_code=502, detail=str(exception)) from exception
