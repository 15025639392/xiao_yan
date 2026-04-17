from __future__ import annotations

import json
from typing import Any

from app.llm.schemas import ChatMessage


def extract_chat_content(content: object) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        fragments: list[str] = []
        for part in content:
            if isinstance(part, str):
                fragments.append(part)
                continue
            if not isinstance(part, dict):
                continue
            text = part.get("text")
            if isinstance(text, str):
                fragments.append(text)
        return "".join(fragments)
    return ""


def extract_chat_text_from_response(payload: dict[str, Any]) -> str:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    first_choice = choices[0]
    if not isinstance(first_choice, dict):
        return ""
    message = first_choice.get("message")
    if not isinstance(message, dict):
        return ""
    return extract_chat_content(message.get("content"))


def build_chat_messages(
    messages: list[ChatMessage],
    *,
    instructions: str | None = None,
) -> list[dict[str, object]]:
    system_segments: list[str] = []
    if instructions:
        system_segments.append(instructions)

    payload_messages: list[dict[str, object]] = []
    for message in messages:
        if message.role == "system":
            system_segments.append(message.content)
            continue
        payload_messages.append(message.model_dump())

    if system_segments:
        merged_system_content = "\n\n".join(segment for segment in system_segments if segment)
        if merged_system_content:
            payload_messages.insert(0, {"role": "system", "content": merged_system_content})

    return payload_messages


def normalize_chat_tools(tools: list[dict[str, Any]] | None) -> list[dict[str, Any]] | None:
    if not tools:
        return None

    normalized_tools: list[dict[str, Any]] = []
    for tool in tools:
        if not isinstance(tool, dict):
            continue
        if tool.get("type") != "function":
            normalized_tools.append(tool)
            continue
        function_payload = tool.get("function")
        if isinstance(function_payload, dict):
            normalized_tools.append(tool)
            continue
        name = tool.get("name")
        if not isinstance(name, str) or not name:
            continue
        mapped_function: dict[str, object] = {"name": name}
        description = tool.get("description")
        if isinstance(description, str) and description:
            mapped_function["description"] = description
        parameters = tool.get("parameters")
        if isinstance(parameters, dict):
            mapped_function["parameters"] = parameters
        normalized_tools.append(
            {
                "type": "function",
                "function": mapped_function,
            }
        )
    return normalized_tools


def extract_response_message_text(item: dict[str, Any]) -> str:
    content = item.get("content")
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""

    fragments: list[str] = []
    for content_item in content:
        if not isinstance(content_item, dict):
            continue
        text = content_item.get("text")
        if isinstance(text, str):
            fragments.append(text)
    return "".join(fragments)


def convert_input_items_to_chat_messages(
    input_items: list[dict[str, Any]],
    *,
    instructions: str | None = None,
) -> list[dict[str, object]]:
    system_segments: list[str] = []
    messages: list[dict[str, object]] = []
    if instructions:
        system_segments.append(instructions)

    index = 0
    while index < len(input_items):
        item = input_items[index]
        index += 1
        if not isinstance(item, dict):
            continue

        role = item.get("role")
        if isinstance(role, str):
            content = extract_chat_content(item.get("content"))
            if role == "system":
                if content:
                    system_segments.append(content)
            else:
                messages.append(
                    {
                        "role": role,
                        "content": content,
                    }
                )
            continue

        item_type = item.get("type")
        if item_type == "message":
            mapped_role = item.get("role", "assistant")
            content = extract_response_message_text(item)
            if mapped_role == "system":
                if content:
                    system_segments.append(content)
            else:
                messages.append(
                    {
                        "role": mapped_role,
                        "content": content,
                    }
                )
            continue

        if item_type == "function_call":
            tool_calls: list[dict[str, object]] = []
            current_item: dict[str, Any] | None = item
            while isinstance(current_item, dict) and current_item.get("type") == "function_call":
                call_id = current_item.get("call_id")
                function_name = current_item.get("name")
                raw_arguments = current_item.get("arguments", "{}")
                if isinstance(call_id, str) and isinstance(function_name, str):
                    if isinstance(raw_arguments, dict):
                        arguments = json.dumps(raw_arguments, ensure_ascii=False)
                    elif isinstance(raw_arguments, str):
                        arguments = raw_arguments
                    else:
                        arguments = "{}"

                    tool_calls.append(
                        {
                            "id": call_id,
                            "type": "function",
                            "function": {
                                "name": function_name,
                                "arguments": arguments,
                            },
                        }
                    )

                if index >= len(input_items):
                    break
                next_item = input_items[index]
                if not isinstance(next_item, dict) or next_item.get("type") != "function_call":
                    break
                current_item = next_item
                index += 1

            if tool_calls:
                messages.append(
                    {
                        "role": "assistant",
                        "content": "",
                        "tool_calls": tool_calls,
                    }
                )
            continue

        if item_type == "function_call_output":
            call_id = item.get("call_id")
            if not isinstance(call_id, str):
                continue
            output = item.get("output", "")
            if isinstance(output, str):
                output_text = output
            else:
                output_text = json.dumps(output, ensure_ascii=False)
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call_id,
                    "content": output_text,
                }
            )

    if system_segments:
        merged_system_content = "\n\n".join(segment for segment in system_segments if segment)
        if merged_system_content:
            messages.insert(0, {"role": "system", "content": merged_system_content})

    return messages


def normalize_chat_completion_response(payload: dict[str, Any]) -> dict[str, object]:
    normalized: dict[str, object] = {"id": payload.get("id")}
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        normalized["output"] = []
        normalized["output_text"] = ""
        return normalized

    first_choice = choices[0]
    if not isinstance(first_choice, dict):
        normalized["output"] = []
        normalized["output_text"] = ""
        return normalized

    message = first_choice.get("message")
    if not isinstance(message, dict):
        normalized["output"] = []
        normalized["output_text"] = ""
        return normalized

    output_items: list[dict[str, object]] = []
    has_tool_calls = False
    content_text = extract_chat_content(message.get("content"))
    if content_text:
        output_items.append(
            {
                "type": "message",
                "role": "assistant",
                "content": [
                    {
                        "type": "output_text",
                        "text": content_text,
                    }
                ],
            }
        )
    tool_calls = message.get("tool_calls")
    if isinstance(tool_calls, list):
        for tool_call in tool_calls:
            if not isinstance(tool_call, dict):
                continue
            call_id = tool_call.get("id")
            function_payload = tool_call.get("function")
            if not isinstance(call_id, str) or not isinstance(function_payload, dict):
                continue
            function_name = function_payload.get("name")
            raw_arguments = function_payload.get("arguments", "{}")
            if not isinstance(function_name, str):
                continue
            if isinstance(raw_arguments, dict):
                arguments = json.dumps(raw_arguments, ensure_ascii=False)
            elif isinstance(raw_arguments, str):
                arguments = raw_arguments
            else:
                arguments = "{}"
            output_items.append(
                {
                    "type": "function_call",
                    "call_id": call_id,
                    "name": function_name,
                    "arguments": arguments,
                }
            )
            has_tool_calls = True

    normalized["output"] = output_items
    normalized["output_text"] = "" if has_tool_calls else content_text
    return normalized
