from __future__ import annotations

import json
from collections.abc import Generator, Iterable

from app.llm.gateway_events import (
    extract_error_message,
    extract_output_text,
    extract_response_id,
    iter_sse_events,
)


def iter_openai_responses_stream_events(lines: Iterable[str]) -> Generator[dict[str, str | None], None, None]:
    output_fragments: list[str] = []
    current_response_id: str | None = None

    for event_name, event_data in iter_sse_events(lines):
        if event_data == "[DONE]":
            break

        payload = _load_sse_payload(event_data)
        if payload is None:
            continue

        if event_name == "response.created":
            current_response_id = extract_response_id(payload) or current_response_id
            yield {
                "type": "response_started",
                "response_id": current_response_id,
            }
            continue

        if event_name == "response.output_text.delta":
            delta = payload.get("delta") or ""
            if delta:
                output_fragments.append(delta)
                yield {
                    "type": "text_delta",
                    "delta": delta,
                }
            continue

        if event_name in {
            "response.output_item.added",
            "response.output_item.done",
            "response.content_part.added",
            "response.content_part.done",
            "response.function_call_arguments.delta",
            "response.function_call_arguments.done",
        }:
            continue

        if event_name == "response.completed":
            completed_response = payload.get("response", payload)
            current_response_id = extract_response_id(payload) or current_response_id
            output_text = (
                extract_output_text(completed_response)
                if isinstance(completed_response, dict)
                and (completed_response.get("output") or completed_response.get("output_text"))
                else "".join(output_fragments)
            )
            yield {
                "type": "response_completed",
                "response_id": current_response_id,
                "output_text": output_text,
            }
            continue

        if event_name == "error":
            yield {
                "type": "response_failed",
                "error": extract_error_message(payload),
            }


def _load_sse_payload(event_data: str) -> dict | None:
    try:
        payload = json.loads(event_data)
    except json.JSONDecodeError:
        return None
    if isinstance(payload, dict):
        return payload
    return None
