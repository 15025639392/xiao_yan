from __future__ import annotations

from collections.abc import Generator
from dataclasses import dataclass

from app.llm.openai_responses_stream_wire import iter_openai_responses_stream_events
from app.llm.responses_base import ResponsesWireAdapter


@dataclass(frozen=True)
class OpenAIResponsesWireAdapter(ResponsesWireAdapter):
    def iter_stream_events(self, lines) -> Generator[dict[str, str | None], None, None]:
        yield from iter_openai_responses_stream_events(lines)
