from __future__ import annotations

from collections.abc import Generator
from dataclasses import dataclass

import httpx

from app.llm.generic_chat_completions_stream_wire import iter_default_chat_completions_stream_events
from app.llm.http_wire import fetch_model_ids
from app.llm.request_wire import (
    build_chat_completions_payload,
    build_chat_completions_tools_payload,
)
from app.llm.response_wire import (
    extract_chat_completions_chat_result,
    normalize_chat_completions_tools_response,
)
from app.llm.schemas import ChatMessage, ChatResult


@dataclass(frozen=True)
class ChatCompletionsWireAdapter:
    def iter_stream_events(self, lines) -> Generator[dict[str, str | None], None, None]:
        yield from iter_default_chat_completions_stream_events(lines)

    def list_models(
        self,
        *,
        client: httpx.Client,
        base_url: str,
        headers: dict[str, str],
    ) -> list[str]:
        return fetch_model_ids(client=client, base_url=base_url, headers=headers)

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
        response = client.post(
            f"{base_url}/chat/completions",
            headers=headers,
            json=build_chat_completions_payload(
                model=model,
                messages=messages,
                instructions=instructions,
            ),
        )
        response.raise_for_status()
        return extract_chat_completions_chat_result(response.json())

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
        del previous_response_id
        response = client.post(
            f"{base_url}/chat/completions",
            headers=headers,
            json=build_chat_completions_tools_payload(
                model=model,
                input_items=input_items,
                instructions=instructions,
                tools=tools,
            ),
        )
        response.raise_for_status()
        return normalize_chat_completions_tools_response(response.json())

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
        with client.stream(
            "POST",
            f"{base_url}/chat/completions",
            headers=headers,
            json=build_chat_completions_payload(
                model=model,
                messages=messages,
                instructions=instructions,
                stream=True,
            ),
        ) as response:
            response.raise_for_status()
            yield from self.iter_stream_events(response.iter_lines())
