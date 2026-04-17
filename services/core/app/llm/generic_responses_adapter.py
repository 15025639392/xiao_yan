from __future__ import annotations

from collections.abc import Generator
from dataclasses import dataclass

from app.llm.generic_responses_stream_wire import iter_default_responses_stream_events
from app.llm.responses_base import ResponsesWireAdapter


@dataclass(frozen=True)
class GenericResponsesWireAdapter(ResponsesWireAdapter):
    def iter_stream_events(self, lines) -> Generator[dict[str, str | None], None, None]:
        yield from iter_default_responses_stream_events(lines)
