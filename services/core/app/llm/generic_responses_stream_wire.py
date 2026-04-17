from __future__ import annotations

from collections.abc import Generator, Iterable

from app.llm.protocol_stream_wire import iter_generic_responses_stream_events


def iter_default_responses_stream_events(lines: Iterable[str]) -> Generator[dict[str, str | None], None, None]:
    yield from iter_generic_responses_stream_events(lines)
