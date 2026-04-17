from __future__ import annotations

import json
from collections.abc import Generator, Iterable

from app.llm.gateway_events import extract_error_message, iter_sse_events


def iter_openai_chat_completions_stream_events(lines: Iterable[str]) -> Generator[dict[str, str | None], None, None]:
    output_fragments: list[str] = []
    current_response_id: str | None = None
    started = False
    completed = False

    for _event_name, event_data in iter_sse_events(lines):
        if event_data == "[DONE]":
            break

        payload = _load_sse_payload(event_data)
        if payload is None or not isinstance(payload, dict):
            continue

        payload_id = payload.get("id")
        if isinstance(payload_id, str):
            current_response_id = payload_id
        if current_response_id and not started:
            started = True
            yield {
                "type": "response_started",
                "response_id": current_response_id,
            }

        if isinstance(payload.get("error"), dict):
            yield {
                "type": "response_failed",
                "error": extract_error_message(payload),
            }
            completed = True
            break

        choices = payload.get("choices")
        if not isinstance(choices, list) or not choices:
            continue
        first_choice = choices[0]
        if not isinstance(first_choice, dict):
            continue

        delta = first_choice.get("delta")
        if isinstance(delta, dict):
            delta_content = delta.get("content")
            if isinstance(delta_content, str) and delta_content:
                output_fragments.append(delta_content)
                yield {
                    "type": "text_delta",
                    "delta": delta_content,
                }
            if isinstance(delta.get("tool_calls"), list):
                pass

        finish_reason = first_choice.get("finish_reason")
        if isinstance(finish_reason, str) and finish_reason and not completed:
            completed = True
            yield {
                "type": "response_completed",
                "response_id": current_response_id,
                "output_text": "".join(output_fragments),
            }

    if not completed:
        yield {
            "type": "response_completed",
            "response_id": current_response_id,
            "output_text": "".join(output_fragments),
        }


def _load_sse_payload(event_data: str) -> dict | None:
    try:
        payload = json.loads(event_data)
    except json.JSONDecodeError:
        return None
    if isinstance(payload, dict):
        return payload
    return None
