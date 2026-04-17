from __future__ import annotations

from collections.abc import Generator
from dataclasses import dataclass

import httpx

from app.llm.chat_completions_base import ChatCompletionsWireAdapter
from app.llm.minimax_chat_completions_stream_wire import iter_minimax_chat_completions_stream_events
from app.llm.provider_defaults import MINIMAX_SUPPORTED_CHAT_MODELS


@dataclass(frozen=True)
class MiniMaxChatCompletionsWireAdapter(ChatCompletionsWireAdapter):
    def iter_stream_events(self, lines) -> Generator[dict[str, str | None], None, None]:
        yield from iter_minimax_chat_completions_stream_events(lines)

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
