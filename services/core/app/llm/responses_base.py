from __future__ import annotations

from collections.abc import Generator
from dataclasses import dataclass

import httpx

from app.llm.generic_responses_stream_wire import iter_default_responses_stream_events
from app.llm.http_wire import fetch_model_ids
from app.llm.request_wire import (
    build_responses_payload,
    build_responses_tools_payload,
)
from app.llm.response_wire import extract_responses_chat_result
from app.llm.schemas import ChatMessage, ChatResult


@dataclass(frozen=True)
class ResponsesWireAdapter:
    def iter_stream_events(self, lines) -> Generator[dict[str, str | None], None, None]:
        yield from iter_default_responses_stream_events(lines)

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
            f"{base_url}/responses",
            headers=headers,
            json=build_responses_payload(
                model=model,
                messages=messages,
                instructions=instructions,
            ),
        )
        response.raise_for_status()
        return extract_responses_chat_result(response.json())

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
        response = client.post(
            f"{base_url}/responses",
            headers=headers,
            json=build_responses_tools_payload(
                model=model,
                input_items=input_items,
                instructions=instructions,
                tools=tools,
                previous_response_id=previous_response_id,
            ),
        )
        response.raise_for_status()
        return response.json()

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
            f"{base_url}/responses",
            headers=headers,
            json=build_responses_payload(
                model=model,
                messages=messages,
                instructions=instructions,
            )
            | {"stream": True},
        ) as response:
            response.raise_for_status()
            yield from self.iter_stream_events(response.iter_lines())
