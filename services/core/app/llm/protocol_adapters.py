from __future__ import annotations

from collections.abc import Generator
from dataclasses import dataclass
from typing import Protocol

import httpx

from app.llm.http_wire import fetch_model_ids
from app.llm.provider_defaults import MINIMAX_SUPPORTED_CHAT_MODELS
from app.llm.request_wire import (
    build_chat_completions_payload,
    build_chat_completions_tools_payload,
    build_responses_payload,
    build_responses_tools_payload,
)
from app.llm.response_wire import (
    extract_chat_completions_chat_result,
    extract_responses_chat_result,
    normalize_chat_completions_tools_response,
)
from app.llm.schemas import ChatMessage, ChatResult
from app.llm.stream_wire import (
    iter_chat_completions_stream_events,
    iter_responses_stream_events,
)


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


@dataclass(frozen=True)
class ResponsesWireAdapter:
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
            yield from iter_responses_stream_events(response.iter_lines())


@dataclass(frozen=True)
class ChatCompletionsWireAdapter:
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
            yield from iter_chat_completions_stream_events(response.iter_lines())


@dataclass(frozen=True)
class OpenAIResponsesWireAdapter(ResponsesWireAdapter):
    pass


@dataclass(frozen=True)
class OpenAIChatCompletionsWireAdapter(ChatCompletionsWireAdapter):
    pass


@dataclass(frozen=True)
class MiniMaxChatCompletionsWireAdapter(ChatCompletionsWireAdapter):
    def list_models(
        self,
        *,
        client: httpx.Client,
        base_url: str,
        headers: dict[str, str],
    ) -> list[str]:
        try:
            return super().list_models(client=client, base_url=base_url, headers=headers)
        except httpx.HTTPStatusError as error:
            if error.response.status_code == 404:
                return list(MINIMAX_SUPPORTED_CHAT_MODELS)
            raise


@dataclass(frozen=True)
class DeepSeekChatCompletionsWireAdapter(ChatCompletionsWireAdapter):
    pass


@dataclass(frozen=True)
class GenericResponsesWireAdapter(ResponsesWireAdapter):
    pass


@dataclass(frozen=True)
class GenericChatCompletionsWireAdapter(ChatCompletionsWireAdapter):
    pass


def get_wire_adapter(provider_id: str, wire_api: str) -> ChatWireAdapter:
    normalized_provider = (provider_id or "").strip().lower()
    if normalized_provider == "openai":
        if wire_api == "responses":
            return OpenAIResponsesWireAdapter()
        if wire_api == "chat":
            return OpenAIChatCompletionsWireAdapter()
    if normalized_provider == "minimaxi" and wire_api == "chat":
        return MiniMaxChatCompletionsWireAdapter()
    if normalized_provider == "deepseek" and wire_api == "chat":
        return DeepSeekChatCompletionsWireAdapter()
    if wire_api == "responses":
        return GenericResponsesWireAdapter()
    if wire_api == "chat":
        return GenericChatCompletionsWireAdapter()
    raise ValueError(f"unsupported wire_api: {wire_api}")
