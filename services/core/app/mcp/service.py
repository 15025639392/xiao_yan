from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from app.mcp.stdio_client import StdioMcpClient

_NAME_SANITIZER = re.compile(r"[^a-zA-Z0-9_]+")


@dataclass(slots=True)
class ChatMcpCallRegistry:
    tools: list[dict[str, Any]]
    tool_to_server: dict[str, dict[str, Any]]


def _sanitize_name(value: str) -> str:
    normalized = _NAME_SANITIZER.sub("_", value.strip())
    normalized = normalized.strip("_")
    if not normalized:
        return "tool"
    return normalized


def _build_prefixed_tool_name(server_id: str, tool_name: str) -> str:
    return f"mcp__{_sanitize_name(server_id)}__{_sanitize_name(tool_name)}"


def _build_tool_definition(prefixed_name: str, tool_payload: dict[str, Any]) -> dict[str, Any]:
    description = tool_payload.get("description")
    if not isinstance(description, str):
        description = ""

    parameters = tool_payload.get("inputSchema")
    if not isinstance(parameters, dict):
        parameters = {"type": "object", "properties": {}, "additionalProperties": True}

    return {
        "type": "function",
        "name": prefixed_name,
        "description": description or f"MCP tool {prefixed_name}",
        "parameters": parameters,
    }


def build_chat_mcp_tool_registry(
    *,
    mcp_enabled: bool,
    configured_servers: list[dict[str, Any]],
    selected_server_ids: list[str] | None,
) -> ChatMcpCallRegistry:
    if not mcp_enabled:
        return ChatMcpCallRegistry(tools=[], tool_to_server={})

    selected: set[str] | None
    if selected_server_ids is None:
        selected = None
    else:
        selected = {
            item.strip().lower()
            for item in selected_server_ids
            if isinstance(item, str) and item.strip()
        }
        # Explicitly passing an empty selection means "disable MCP tools for this request".
        if not selected:
            return ChatMcpCallRegistry(tools=[], tool_to_server={})

    tool_defs: list[dict[str, Any]] = []
    tool_mapping: dict[str, dict[str, Any]] = {}

    for server in configured_servers:
        if not isinstance(server, dict):
            continue
        server_id_raw = server.get("server_id")
        if not isinstance(server_id_raw, str) or not server_id_raw.strip():
            continue
        server_id = server_id_raw.strip().lower()
        if not bool(server.get("enabled", True)):
            continue
        if selected is not None and server_id not in selected:
            continue

        command = server.get("command")
        if not isinstance(command, str) or not command.strip():
            continue

        args = server.get("args")
        if not isinstance(args, list):
            args = []
        safe_args = [item for item in args if isinstance(item, str)]

        cwd = server.get("cwd")
        safe_cwd = cwd if isinstance(cwd, str) and cwd.strip() else None

        env = server.get("env")
        safe_env = env if isinstance(env, dict) else {}

        timeout_seconds = server.get("timeout_seconds", 20)
        try:
            timeout = int(timeout_seconds)
        except Exception:  # noqa: BLE001
            timeout = 20

        client: StdioMcpClient | None = None
        try:
            client = StdioMcpClient(
                command=command.strip(),
                args=safe_args,
                cwd=safe_cwd,
                env={str(k): str(v) for k, v in safe_env.items()},
                timeout_seconds=timeout,
            )
            client.initialize()
            server_tools = client.list_tools()
        except Exception:  # noqa: BLE001
            server_tools = []
        finally:
            if client is not None:
                client.close()

        for tool in server_tools:
            tool_name = tool.get("name")
            if not isinstance(tool_name, str) or not tool_name.strip():
                continue
            prefixed_name = _build_prefixed_tool_name(server_id, tool_name)
            unique_name = prefixed_name
            suffix = 1
            while unique_name in tool_mapping:
                suffix += 1
                unique_name = f"{prefixed_name}_{suffix}"

            tool_defs.append(_build_tool_definition(unique_name, tool))
            tool_mapping[unique_name] = {
                "server": server,
                "tool_name": tool_name,
                "server_id": server_id,
            }

    return ChatMcpCallRegistry(tools=tool_defs, tool_to_server=tool_mapping)


def call_chat_mcp_tool(
    registry: ChatMcpCallRegistry,
    *,
    tool_name: str,
    arguments: dict[str, Any],
) -> str | None:
    mapping = registry.tool_to_server.get(tool_name)
    if mapping is None:
        return None

    server = mapping["server"]
    command = server.get("command")
    if not isinstance(command, str) or not command.strip():
        return json.dumps(
            {
                "error": "invalid mcp server command",
                "mcp_server_id": mapping.get("server_id"),
            },
            ensure_ascii=False,
        )

    args = server.get("args")
    if not isinstance(args, list):
        args = []
    safe_args = [item for item in args if isinstance(item, str)]

    cwd = server.get("cwd")
    safe_cwd = cwd if isinstance(cwd, str) and cwd.strip() else None

    env = server.get("env")
    safe_env = env if isinstance(env, dict) else {}

    timeout_seconds = server.get("timeout_seconds", 20)
    try:
        timeout = int(timeout_seconds)
    except Exception:  # noqa: BLE001
        timeout = 20

    client: StdioMcpClient | None = None
    try:
        client = StdioMcpClient(
            command=command.strip(),
            args=safe_args,
            cwd=safe_cwd,
            env={str(k): str(v) for k, v in safe_env.items()},
            timeout_seconds=timeout,
        )
        client.initialize()
        result = client.call_tool(str(mapping["tool_name"]), arguments)
        return json.dumps(
            {
                "mcp_server_id": mapping.get("server_id"),
                "tool_name": mapping.get("tool_name"),
                "result": result,
            },
            ensure_ascii=False,
        )
    except Exception as exc:  # noqa: BLE001
        return json.dumps(
            {
                "error": str(exc),
                "mcp_server_id": mapping.get("server_id"),
                "tool_name": mapping.get("tool_name"),
            },
            ensure_ascii=False,
        )
    finally:
        if client is not None:
            client.close()
