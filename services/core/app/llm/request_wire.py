from __future__ import annotations

from typing import Any

from app.llm.chat_wire import build_chat_messages, convert_input_items_to_chat_messages, normalize_chat_tools
from app.llm.schemas import ChatMessage


def build_responses_payload(
    *,
    model: str,
    messages: list[ChatMessage],
    instructions: str | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "model": model,
        "input": [message.model_dump() for message in messages],
    }
    if instructions:
        payload["instructions"] = instructions
    return payload


def build_responses_tools_payload(
    *,
    model: str,
    input_items: list[dict[str, Any]],
    instructions: str | None = None,
    tools: list[dict[str, Any]] | None = None,
    previous_response_id: str | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "model": model,
        "input": input_items,
    }
    if instructions:
        payload["instructions"] = instructions
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"
    if previous_response_id:
        payload["previous_response_id"] = previous_response_id
    return payload


def build_chat_completions_payload(
    *,
    model: str,
    messages: list[ChatMessage],
    instructions: str | None = None,
    stream: bool = False,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "model": model,
        "messages": build_chat_messages(messages, instructions=instructions),
    }
    if stream:
        payload["stream"] = True
    return payload


def build_chat_completions_tools_payload(
    *,
    model: str,
    input_items: list[dict[str, Any]],
    instructions: str | None = None,
    tools: list[dict[str, Any]] | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "model": model,
        "messages": convert_input_items_to_chat_messages(input_items, instructions=instructions),
    }
    normalized_tools = normalize_chat_tools(tools)
    if normalized_tools:
        payload["tools"] = normalized_tools
        payload["tool_choice"] = "auto"
    return payload
