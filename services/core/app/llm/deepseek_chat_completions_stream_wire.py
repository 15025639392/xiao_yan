from __future__ import annotations

from collections.abc import Generator, Iterable

from app.llm.protocol_stream_wire import iter_configured_chat_completions_stream_events


def iter_deepseek_chat_completions_stream_events(lines: Iterable[str]) -> Generator[dict[str, str | None], None, None]:
    # DeepSeek exposes reasoning as delta.reasoning_content beside final delta.content.
    yield from iter_configured_chat_completions_stream_events(lines, reasoning_field="reasoning_content")
