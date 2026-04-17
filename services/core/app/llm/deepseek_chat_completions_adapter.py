from __future__ import annotations

from collections.abc import Generator
from dataclasses import dataclass

from app.llm.chat_completions_base import ChatCompletionsWireAdapter
from app.llm.deepseek_chat_completions_stream_wire import iter_deepseek_chat_completions_stream_events


@dataclass(frozen=True)
class DeepSeekChatCompletionsWireAdapter(ChatCompletionsWireAdapter):
    def iter_stream_events(self, lines) -> Generator[dict[str, str | None], None, None]:
        yield from iter_deepseek_chat_completions_stream_events(lines)
