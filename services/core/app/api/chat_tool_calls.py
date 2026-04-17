from __future__ import annotations

import json
from typing import Any

from app.mcp import ChatMcpCallRegistry, call_chat_mcp_tool


def extract_function_calls(response_payload: dict[str, Any]) -> list[tuple[str, str, dict[str, Any]]]:
    function_calls: list[tuple[str, str, dict[str, Any]]] = []
    outputs = response_payload.get("output", [])
    if not isinstance(outputs, list):
        return function_calls

    for item in outputs:
        if not isinstance(item, dict) or item.get("type") != "function_call":
            continue

        call_id = item.get("call_id") or item.get("id")
        tool_name = item.get("name")
        raw_arguments = item.get("arguments")
        if not isinstance(call_id, str) or not call_id:
            continue
        if not isinstance(tool_name, str) or not tool_name:
            continue

        arguments: dict[str, Any] = {}
        if isinstance(raw_arguments, dict):
            arguments = raw_arguments
        elif isinstance(raw_arguments, str) and raw_arguments.strip():
            try:
                parsed = json.loads(raw_arguments)
            except json.JSONDecodeError:
                parsed = {}
            if isinstance(parsed, dict):
                arguments = parsed

        function_calls.append((call_id, tool_name, arguments))

    return function_calls


def build_function_call_signature(function_calls: list[tuple[str, str, dict[str, Any]]]) -> str:
    normalized = [
        {
            "call_id": call_id,
            "tool_name": tool_name,
            "arguments": arguments,
        }
        for call_id, tool_name, arguments in function_calls
    ]
    return json.dumps(normalized, ensure_ascii=False, sort_keys=True)


def extract_output_text(response_payload: dict[str, Any]) -> str:
    output_text = response_payload.get("output_text")
    if isinstance(output_text, str) and output_text.strip():
        return output_text

    segments: list[str] = []
    outputs = response_payload.get("output", [])
    if not isinstance(outputs, list):
        return ""

    for item in outputs:
        if not isinstance(item, dict):
            continue
        if item.get("type") == "message":
            content_items = item.get("content", [])
            if not isinstance(content_items, list):
                continue
            for content_item in content_items:
                if not isinstance(content_item, dict):
                    continue
                text = content_item.get("text")
                if content_item.get("type") == "output_text" and isinstance(text, str) and text:
                    segments.append(text)

    return "".join(segments)


def execute_tool_call(
    file_tools: Any,
    tool_name: str,
    arguments: dict[str, Any],
    *,
    file_policy_args: dict[str, Any] | None = None,
    mcp_registry: ChatMcpCallRegistry | None = None,
) -> str:
    del file_policy_args

    if mcp_registry is not None:
        mcp_result = call_chat_mcp_tool(mcp_registry, tool_name=tool_name, arguments=arguments)
        if mcp_result is not None:
            return mcp_result

    if tool_name == "read_file":
        result = file_tools.read_file(
            str(arguments.get("path", "")),
            max_bytes=int(arguments.get("max_bytes", 0) or 0),
        )
        payload = result.to_dict()
        payload["content"] = result.content
        return json.dumps(payload, ensure_ascii=False)

    if tool_name == "list_directory":
        result = file_tools.list_directory(
            str(arguments.get("path", ".")),
            recursive=bool(arguments.get("recursive", False)),
            pattern=str(arguments["pattern"]) if isinstance(arguments.get("pattern"), str) else None,
        )
        return json.dumps(result.to_dict(), ensure_ascii=False)

    if tool_name == "search_files":
        result = file_tools.search_content(
            str(arguments.get("query", "")),
            str(arguments.get("search_path", ".")),
            file_pattern=str(arguments["file_pattern"]) if isinstance(arguments.get("file_pattern"), str) else "*.py",
            max_results=int(arguments.get("max_results", 20) or 20),
        )
        return json.dumps(result.to_dict(), ensure_ascii=False)

    if tool_name == "write_file":
        result = file_tools.write_file(
            str(arguments.get("path", "")),
            str(arguments.get("content", "")),
            create_dirs=bool(arguments.get("create_dirs", True)),
        )
        return json.dumps(result.to_dict(), ensure_ascii=False)

    return json.dumps({"error": f"unsupported tool: {tool_name}"}, ensure_ascii=False)
