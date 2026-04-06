from __future__ import annotations

from collections.abc import Generator


def extract_output_text(data: dict) -> str:
    if data.get("output_text"):
        return data["output_text"]

    for item in data.get("output", []):
        if item.get("type") != "message":
            continue

        for content in item.get("content", []):
            if content.get("type") not in {"output_text", "text"}:
                continue

            text = content.get("text")
            if text:
                return text

    raise ValueError("response payload did not contain output text")


def extract_response_id(data: dict) -> str | None:
    if isinstance(data.get("response"), dict):
        response_id = data["response"].get("id")
        if response_id:
            return response_id
    response_id = data.get("id")
    if isinstance(response_id, str):
        return response_id
    return None


def extract_error_message(data: dict) -> str:
    if isinstance(data.get("error"), dict):
        message = data["error"].get("message")
        if message:
            return str(message)
    message = data.get("message")
    if message:
        return str(message)
    return "streaming failed"


def iter_sse_events(lines) -> Generator[tuple[str | None, str], None, None]:
    event_name: str | None = None
    data_lines: list[str] = []

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            if data_lines:
                yield event_name, "\n".join(data_lines)
            event_name = None
            data_lines = []
            continue

        if line.startswith("event:"):
            event_name = line.removeprefix("event:").strip()
            continue

        if line.startswith("data:"):
            data_lines.append(line.removeprefix("data:").strip())

    if data_lines:
        yield event_name, "\n".join(data_lines)


__all__ = [
    "extract_output_text",
    "extract_response_id",
    "extract_error_message",
    "iter_sse_events",
]
