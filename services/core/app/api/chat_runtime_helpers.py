from __future__ import annotations

import httpx
from fastapi import Request

from app.memory.observability import MemoryObservabilityTracker


def merge_chat_stream_content(current_content: str, delta: str) -> str:
    if not current_content:
        return delta
    if not delta:
        return current_content
    if delta.startswith(current_content):
        return delta
    if current_content.startswith(delta) or delta in current_content:
        return current_content
    max_overlap = min(len(current_content), len(delta))
    for overlap in range(max_overlap, 0, -1):
        if current_content[-overlap:] == delta[:overlap]:
            return f"{current_content}{delta[overlap:]}"
    return f"{current_content}{delta}"


def should_fallback_to_stream_without_tools(exception: Exception) -> bool:
    if not isinstance(exception, httpx.HTTPStatusError):
        return False
    status_code = exception.response.status_code if exception.response is not None else None
    return status_code in {400, 404, 405, 415, 422, 501}


def get_observability_tracker(request: Request) -> MemoryObservabilityTracker | None:
    tracker = getattr(request.app.state, "memory_observability_tracker", None)
    if isinstance(tracker, MemoryObservabilityTracker):
        return tracker
    return None
