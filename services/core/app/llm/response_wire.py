from __future__ import annotations

from collections.abc import Iterable

from app.llm.chat_wire import extract_chat_text_from_response, normalize_chat_completion_response
from app.llm.gateway_events import extract_output_text
from app.llm.schemas import ChatResult


def extract_responses_chat_result(payload: dict) -> ChatResult:
    return ChatResult(
        response_id=payload.get("id"),
        output_text=extract_output_text(payload),
    )


def extract_chat_completions_chat_result(payload: dict) -> ChatResult:
    return ChatResult(
        response_id=payload.get("id"),
        output_text=extract_chat_text_from_response(payload),
    )


def normalize_chat_completions_tools_response(payload: dict) -> dict:
    return normalize_chat_completion_response(payload)


def create_chat_result_from_stream_events(events: Iterable[dict[str, str | None]]) -> ChatResult:
    response_id: str | None = None
    output_fragments: list[str] = []

    for event in events:
        event_type = event.get("type")
        if event_type == "response_started":
            started_response_id = event.get("response_id")
            if isinstance(started_response_id, str) and started_response_id:
                response_id = started_response_id
            continue

        if event_type == "text_delta":
            delta = event.get("delta")
            if isinstance(delta, str) and delta:
                output_fragments.append(delta)
            continue

        if event_type == "response_failed":
            error_message = event.get("error")
            if isinstance(error_message, str) and error_message:
                raise RuntimeError(error_message)
            raise RuntimeError("streaming fallback failed")

        if event_type == "response_completed":
            completed_response_id = event.get("response_id")
            if isinstance(completed_response_id, str) and completed_response_id:
                response_id = completed_response_id
            completed_output = event.get("output_text")
            if isinstance(completed_output, str) and completed_output:
                return ChatResult(response_id=response_id, output_text=completed_output)

    return ChatResult(response_id=response_id, output_text="".join(output_fragments))
