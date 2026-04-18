from collections.abc import Generator

import httpx

from app.config import LLMProviderConfig
from app.llm.adapter_factory import get_wire_adapter as _get_wire_adapter
from app.llm.gateway_bootstrap import (
    build_gateway_init_kwargs as _build_gateway_init_kwargs,
    select_chat_provider_config as _select_chat_provider_config,
)
from app.llm.http_wire import build_auth_headers as _build_auth_headers
from app.llm.response_wire import (
    create_chat_result_from_stream_events as _create_chat_result_from_stream_events,
)
from app.llm.schemas import ChatMessage, ChatResult


class ChatGateway:
    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str = "https://api.openai.com/v1",
        wire_api: str = "responses",
        provider_id: str = "",
        http_client: httpx.Client | None = None,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.wire_api = wire_api
        self.provider_id = provider_id.strip().lower()
        self._http_client = http_client or httpx.Client(timeout=httpx.Timeout(180.0, connect=10.0))

    @classmethod
    def from_env(cls) -> "ChatGateway":
        return cls.from_provider_config(_select_chat_provider_config())

    @classmethod
    def from_provider_config(
        cls,
        provider_config: LLMProviderConfig,
        *,
        model: str | None = None,
        http_client: httpx.Client | None = None,
    ) -> "ChatGateway":
        kwargs = _build_gateway_init_kwargs(provider_config, model=model, http_client=http_client)
        kwargs["provider_id"] = provider_config.provider_id
        return cls(**kwargs)

    def _auth_headers(self) -> dict[str, str]:
        return _build_auth_headers(self.api_key)

    def _wire_adapter(self):
        return _get_wire_adapter(self.provider_id, self.wire_api)

    def _create_response_from_stream_fallback(
        self,
        messages: list[ChatMessage],
        instructions: str | None = None,
    ) -> ChatResult:
        return _create_chat_result_from_stream_events(self.stream_response(messages, instructions=instructions))

    def create_response(
        self,
        messages: list[ChatMessage],
        instructions: str | None = None,
    ) -> ChatResult:
        try:
            result = self._wire_adapter().create_response(
                client=self._http_client,
                base_url=self.base_url,
                headers=self._auth_headers(),
                model=self.model,
                messages=messages,
                instructions=instructions,
            )
        except ValueError:
            return self._create_response_from_stream_fallback(messages, instructions=instructions)
        if self.wire_api == "chat" and not result.output_text:
            fallback_result = self._create_response_from_stream_fallback(messages, instructions=instructions)
            if fallback_result.output_text:
                return fallback_result
        return result

    def create_response_with_tools(
        self,
        input_items: list[dict],
        *,
        instructions: str | None = None,
        tools: list[dict] | None = None,
        previous_response_id: str | None = None,
    ) -> dict:
        return self._wire_adapter().create_response_with_tools(
            client=self._http_client,
            base_url=self.base_url,
            headers=self._auth_headers(),
            model=self.model,
            input_items=input_items,
            instructions=instructions,
            tools=tools,
            previous_response_id=previous_response_id,
        )

    def list_models(self) -> list[str]:
        return self._wire_adapter().list_models(
            client=self._http_client,
            base_url=self.base_url,
            headers=self._auth_headers(),
        )

    def stream_response(
        self,
        messages: list[ChatMessage],
        instructions: str | None = None,
    ) -> Generator[dict[str, str | None], None, None]:
        yield from self._wire_adapter().stream_response(
            client=self._http_client,
            base_url=self.base_url,
            headers=self._auth_headers(),
            model=self.model,
            messages=messages,
            instructions=instructions,
        )

    def close(self) -> None:
        self._http_client.close()
