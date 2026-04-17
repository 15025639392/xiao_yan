from __future__ import annotations

from collections.abc import Generator
from typing import Protocol

import httpx

from app.llm.schemas import ChatMessage, ChatResult


class ChatWireAdapter(Protocol):
    def list_models(
        self,
        *,
        client: httpx.Client,
        base_url: str,
        headers: dict[str, str],
    ) -> list[str]:
        ...

    def create_response(
        self,
        *,
        client: httpx.Client,
        base_url: str,
        headers: dict[str, str],
        model: str,
        messages: list[ChatMessage],
        instructions: str | None = None,
    ) -> ChatResult:
        ...

    def create_response_with_tools(
        self,
        *,
        client: httpx.Client,
        base_url: str,
        headers: dict[str, str],
        model: str,
        input_items: list[dict],
        instructions: str | None = None,
        tools: list[dict] | None = None,
        previous_response_id: str | None = None,
    ) -> dict:
        ...

    def stream_response(
        self,
        *,
        client: httpx.Client,
        base_url: str,
        headers: dict[str, str],
        model: str,
        messages: list[ChatMessage],
        instructions: str | None = None,
    ) -> Generator[dict[str, str | None], None, None]:
        ...
