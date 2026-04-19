from __future__ import annotations

from threading import Lock
from typing import Any, ClassVar, Literal

from app.config import (
    get_chat_context_limit,
    get_chat_model,
    get_chat_provider,
    get_chat_read_timeout_seconds,
)
from app.runtime_ext.capability_policy_state import CapabilityPolicyState

FolderAccessLevel = Literal["read_only", "full_access"]
CHAT_MCP_SERVER_MAX_ENTRIES = 32


def _normalize_chat_mcp_server_id(value: str) -> str:
    normalized = value.strip().lower()
    if not normalized:
        raise ValueError("chat mcp server_id must not be empty")
    return normalized


def _normalize_chat_mcp_server_payload(payload: dict[str, Any]) -> dict[str, Any]:
    server_id_raw = payload.get("server_id")
    command_raw = payload.get("command")
    if not isinstance(server_id_raw, str):
        raise ValueError("chat mcp server_id must be a string")
    if not isinstance(command_raw, str):
        raise ValueError("chat mcp command must be a string")

    server_id = _normalize_chat_mcp_server_id(server_id_raw)
    command = command_raw.strip()
    if not command:
        raise ValueError("chat mcp command must not be empty")

    args_raw = payload.get("args", [])
    if args_raw is None:
        args_raw = []
    if not isinstance(args_raw, list):
        raise ValueError("chat mcp args must be a list")
    args = [item.strip() for item in args_raw if isinstance(item, str) and item.strip()]

    cwd_raw = payload.get("cwd")
    if cwd_raw is None:
        cwd = None
    elif isinstance(cwd_raw, str):
        cwd = cwd_raw.strip() or None
    else:
        raise ValueError("chat mcp cwd must be a string or null")

    env_raw = payload.get("env", {})
    if env_raw is None:
        env_raw = {}
    if not isinstance(env_raw, dict):
        raise ValueError("chat mcp env must be an object")
    env: dict[str, str] = {}
    for key, value in env_raw.items():
        if not isinstance(key, str) or not key.strip():
            raise ValueError("chat mcp env keys must be non-empty strings")
        if not isinstance(value, str):
            raise ValueError("chat mcp env values must be strings")
        env[key] = value

    timeout_raw = payload.get("timeout_seconds", 20)
    try:
        timeout_seconds = int(timeout_raw)
    except Exception as exc:  # noqa: BLE001
        raise ValueError("chat mcp timeout_seconds must be an integer") from exc

    return {
        "server_id": server_id,
        "command": command,
        "args": args,
        "cwd": cwd,
        "env": env,
        "enabled": bool(payload.get("enabled", True)),
        "timeout_seconds": max(1, min(120, timeout_seconds)),
    }


class RuntimeConfig:
    _instance: ClassVar["RuntimeConfig"] | None = None
    _instance_lock: ClassVar[Lock] = Lock()
    _capability_policy_state: ClassVar[CapabilityPolicyState] = CapabilityPolicyState()

    @classmethod
    def _initialize_instance(cls) -> "RuntimeConfig":
        instance = super().__new__(cls)
        instance._lock = Lock()
        instance._chat_context_limit = get_chat_context_limit()
        instance._chat_provider = get_chat_provider()
        instance._chat_model = get_chat_model()
        instance._chat_read_timeout_seconds = get_chat_read_timeout_seconds()
        instance._chat_continuous_reasoning_enabled = True
        instance._chat_mcp_enabled = False
        instance._chat_mcp_servers: dict[str, dict[str, Any]] = {}
        instance._folder_permissions: dict[str, FolderAccessLevel] = {}
        cls._capability_policy_state.initialize(instance)
        return instance

    @classmethod
    def _ensure_instance_fields(cls, instance: "RuntimeConfig") -> None:
        if not hasattr(instance, "_lock"):
            instance._lock = Lock()
        with instance._lock:
            if not hasattr(instance, "_chat_context_limit"):
                instance._chat_context_limit = get_chat_context_limit()
            if not hasattr(instance, "_chat_provider"):
                instance._chat_provider = get_chat_provider()
            if not hasattr(instance, "_chat_model"):
                instance._chat_model = get_chat_model()
            if not hasattr(instance, "_chat_read_timeout_seconds"):
                instance._chat_read_timeout_seconds = get_chat_read_timeout_seconds()
            if not hasattr(instance, "_chat_continuous_reasoning_enabled"):
                instance._chat_continuous_reasoning_enabled = True
            if not hasattr(instance, "_chat_mcp_enabled"):
                instance._chat_mcp_enabled = False
            if not hasattr(instance, "_chat_mcp_servers") or not isinstance(instance._chat_mcp_servers, dict):
                instance._chat_mcp_servers = {}
            if not hasattr(instance, "_folder_permissions") or not isinstance(instance._folder_permissions, dict):
                instance._folder_permissions = {}
            cls._capability_policy_state.ensure_fields(instance)

    def __new__(cls) -> "RuntimeConfig":
        with cls._instance_lock:
            if cls._instance is None:
                cls._instance = cls._initialize_instance()
            else:
                cls._ensure_instance_fields(cls._instance)
            return cls._instance

    @property
    def chat_context_limit(self) -> int:
        with self._lock:
            return self._chat_context_limit

    @chat_context_limit.setter
    def chat_context_limit(self, value: int) -> None:
        with self._lock:
            self._chat_context_limit = max(1, min(20, value))

    @property
    def chat_provider(self) -> str:
        with self._lock:
            return self._chat_provider

    @chat_provider.setter
    def chat_provider(self, value: str) -> None:
        normalized = value.strip()
        if not normalized:
            return
        with self._lock:
            self._chat_provider = normalized

    @property
    def chat_model(self) -> str:
        with self._lock:
            return self._chat_model

    @chat_model.setter
    def chat_model(self, value: str) -> None:
        normalized = value.strip()
        if not normalized:
            return
        with self._lock:
            self._chat_model = normalized

    @property
    def chat_read_timeout_seconds(self) -> int:
        with self._lock:
            return self._chat_read_timeout_seconds

    @chat_read_timeout_seconds.setter
    def chat_read_timeout_seconds(self, value: int) -> None:
        with self._lock:
            self._chat_read_timeout_seconds = max(10, min(600, int(value)))

    @property
    def chat_mcp_enabled(self) -> bool:
        with self._lock:
            return bool(self._chat_mcp_enabled)

    @chat_mcp_enabled.setter
    def chat_mcp_enabled(self, value: bool) -> None:
        with self._lock:
            self._chat_mcp_enabled = bool(value)

    @property
    def chat_continuous_reasoning_enabled(self) -> bool:
        with self._lock:
            return bool(self._chat_continuous_reasoning_enabled)

    @chat_continuous_reasoning_enabled.setter
    def chat_continuous_reasoning_enabled(self, value: bool) -> None:
        with self._lock:
            self._chat_continuous_reasoning_enabled = bool(value)

    def list_chat_mcp_servers(self) -> list[dict[str, Any]]:
        with self._lock:
            snapshot = [dict(item) for item in self._chat_mcp_servers.values()]
        return sorted(snapshot, key=lambda item: item["server_id"])

    def replace_chat_mcp_servers(self, servers: list[dict[str, Any]]) -> None:
        normalized_servers: dict[str, dict[str, Any]] = {}
        for raw in servers:
            if not isinstance(raw, dict):
                raise ValueError("chat mcp servers must be objects")
            normalized = _normalize_chat_mcp_server_payload(raw)
            normalized_servers[normalized["server_id"]] = normalized
            if len(normalized_servers) > CHAT_MCP_SERVER_MAX_ENTRIES:
                raise ValueError(f"too many chat mcp servers (max {CHAT_MCP_SERVER_MAX_ENTRIES})")
        with self._lock:
            self._chat_mcp_servers = normalized_servers

    @property
    def capability_shell_policy_revision(self) -> int:
        with self._lock:
            return int(self._capability_shell_policy_revision)

    @property
    def capability_file_policy_revision(self) -> int:
        with self._lock:
            return int(self._capability_file_policy_revision)

    def _append_capability_shell_policy_history_locked(self, *, source: str) -> dict[str, Any]:
        return self._capability_policy_state.append_shell_history(self, source=source)

    def list_capability_shell_policy_history(self, limit: int = 10) -> list[dict[str, Any]]:
        with self._lock:
            return self._capability_policy_state.list_shell_history(self, limit=limit)

    def get_capability_shell_policy(self) -> dict[str, Any]:
        with self._lock:
            return self._capability_policy_state.get_shell_policy(self)

    def update_capability_shell_policy(
        self,
        *,
        allowed_executables: list[str] | None = None,
        allowed_git_subcommands: list[str] | None = None,
        source: str = "manual_update",
    ) -> dict[str, Any]:
        with self._lock:
            return self._capability_policy_state.update_shell_policy(
                self,
                allowed_executables=allowed_executables,
                allowed_git_subcommands=allowed_git_subcommands,
                source=source,
            )

    def _append_capability_file_policy_history_locked(self, *, source: str) -> dict[str, Any]:
        return self._capability_policy_state.append_file_history(self, source=source)

    def list_capability_file_policy_history(self, limit: int = 10) -> list[dict[str, Any]]:
        with self._lock:
            return self._capability_policy_state.list_file_history(self, limit=limit)

    def get_capability_file_policy(self) -> dict[str, Any]:
        with self._lock:
            return self._capability_policy_state.get_file_policy(self)

    def update_capability_file_policy(
        self,
        *,
        max_read_bytes: int | None = None,
        max_write_bytes: int | None = None,
        max_search_results: int | None = None,
        max_list_entries: int | None = None,
        allowed_search_file_patterns: list[str] | None = None,
        source: str = "manual_update",
    ) -> dict[str, Any]:
        with self._lock:
            return self._capability_policy_state.update_file_policy(
                self,
                max_read_bytes=max_read_bytes,
                max_write_bytes=max_write_bytes,
                max_search_results=max_search_results,
                max_list_entries=max_list_entries,
                allowed_search_file_patterns=allowed_search_file_patterns,
                source=source,
            )

    def list_folder_permissions(self) -> list[tuple[str, FolderAccessLevel]]:
        with self._lock:
            entries = list(self._folder_permissions.items())
        return sorted(entries, key=lambda item: item[0])

    def set_folder_permission(self, folder_path: str, access_level: FolderAccessLevel) -> None:
        with self._lock:
            self._folder_permissions[folder_path] = access_level

    def remove_folder_permission(self, folder_path: str) -> bool:
        with self._lock:
            return self._folder_permissions.pop(folder_path, None) is not None

    def clear_folder_permissions(self) -> None:
        with self._lock:
            self._folder_permissions.clear()


def get_runtime_config() -> RuntimeConfig:
    return RuntimeConfig()
