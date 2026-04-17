from __future__ import annotations

from collections.abc import Generator, Iterable

from app.llm.stream_wire import iter_chat_completions_stream_events, iter_responses_stream_events


def iter_generic_responses_stream_events(lines: Iterable[str]) -> Generator[dict[str, str | None], None, None]:
    yield from iter_responses_stream_events(lines)


def iter_generic_chat_completions_stream_events(lines: Iterable[str]) -> Generator[dict[str, str | None], None, None]:
    yield from iter_chat_completions_stream_events(lines)
