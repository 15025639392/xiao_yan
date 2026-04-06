from __future__ import annotations

from threading import Lock
from typing import ClassVar, Literal

from app.config import get_chat_context_limit, get_chat_model, get_chat_provider, get_chat_read_timeout_seconds

FolderAccessLevel = Literal["read_only", "full_access"]


class RuntimeConfig:
    """Runtime-tunable config values."""

    _instance: ClassVar["RuntimeConfig"] | None = None
    _instance_lock: ClassVar[Lock] = Lock()

    @classmethod
    def _initialize_instance(cls) -> "RuntimeConfig":
        instance = super().__new__(cls)
        instance._lock = Lock()
        instance._chat_context_limit = get_chat_context_limit()
        instance._chat_provider = get_chat_provider()
        instance._chat_model = get_chat_model()
        instance._chat_read_timeout_seconds = get_chat_read_timeout_seconds()
        instance._folder_permissions = {}
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
            if not hasattr(instance, "_folder_permissions") or not isinstance(instance._folder_permissions, dict):
                instance._folder_permissions = {}

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
