from __future__ import annotations

from pathlib import Path

from fastapi import HTTPException
from pydantic import BaseModel, Field

from app.mcp import ChatMcpCallRegistry, build_chat_mcp_tool_registry
from app.runtime_ext.runtime_config import FolderAccessLevel, get_runtime_config


class FolderPermissionEntry(BaseModel):
    path: str = Field(..., min_length=1)
    access_level: FolderAccessLevel


class FolderPermissionRequest(BaseModel):
    path: str = Field(..., min_length=1)
    access_level: FolderAccessLevel


class FolderPermissionListResponse(BaseModel):
    permissions: list[FolderPermissionEntry]


class ChatMcpServerEntry(BaseModel):
    server_id: str
    command: str
    args: list[str] = Field(default_factory=list)
    cwd: str | None = None
    enabled: bool = True
    timeout_seconds: int = 20


class ChatMcpServerListResponse(BaseModel):
    enabled: bool
    servers: list[ChatMcpServerEntry]


def normalize_folder_path(raw_path: str) -> Path:
    path = Path(raw_path).expanduser()
    if not path.is_absolute():
        raise HTTPException(status_code=400, detail="folder path must be absolute")
    return path.resolve()


def build_folder_permission_response() -> FolderPermissionListResponse:
    config = get_runtime_config()
    entries = [
        FolderPermissionEntry(path=path, access_level=access_level)
        for path, access_level in config.list_folder_permissions()
    ]
    return FolderPermissionListResponse(permissions=entries)


def build_chat_mcp_server_response() -> ChatMcpServerListResponse:
    config = get_runtime_config()
    servers = [
        ChatMcpServerEntry(
            server_id=str(item.get("server_id", "")),
            command=str(item.get("command", "")),
            args=[str(arg) for arg in (item.get("args") or []) if isinstance(arg, str)],
            cwd=str(item.get("cwd")) if item.get("cwd") is not None else None,
            enabled=bool(item.get("enabled", True)),
            timeout_seconds=int(item.get("timeout_seconds", 20)),
        )
        for item in config.list_chat_mcp_servers()
        if str(item.get("server_id", "")).strip() and str(item.get("command", "")).strip()
    ]
    return ChatMcpServerListResponse(enabled=config.chat_mcp_enabled, servers=servers)


def build_chat_mcp_registry(requested_server_ids: list[str]) -> ChatMcpCallRegistry:
    config = get_runtime_config()
    return build_chat_mcp_tool_registry(
        mcp_enabled=config.chat_mcp_enabled,
        configured_servers=config.list_chat_mcp_servers(),
        selected_server_ids=requested_server_ids,
    )
