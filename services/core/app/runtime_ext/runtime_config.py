from __future__ import annotations

from typing import ClassVar

from app.config import get_chat_context_limit


class RuntimeConfig:
    """Runtime-tunable config values."""

    _instance: ClassVar["RuntimeConfig"] | None = None

    def __new__(cls) -> "RuntimeConfig":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._chat_context_limit = get_chat_context_limit()
        return cls._instance

    @property
    def chat_context_limit(self) -> int:
        return self._chat_context_limit

    @chat_context_limit.setter
    def chat_context_limit(self, value: int) -> None:
        self._chat_context_limit = max(1, min(20, value))


def get_runtime_config() -> RuntimeConfig:
    return RuntimeConfig()

