from __future__ import annotations

from datetime import datetime

from app.agent.focus_updates import focus_subject_memory_event
from app.domain.models import FocusSubject
from app.memory.models import MemoryEvent
from app.memory.repository import MemoryRepository


def list_recent_events_for_loop(
    memory_repository: MemoryRepository,
    *,
    limit: int = 20,
) -> list[MemoryEvent]:
    return [
        event
        for event in reversed(memory_repository.list_recent(limit=limit))
        if event.source_context != "focus_subject"
    ]


def persist_focus_subject_event(
    *,
    memory_repository: MemoryRepository,
    previous_focus_subject: FocusSubject | None,
    next_focus_subject: FocusSubject,
    now: datetime,
    recent_limit: int = 5,
) -> None:
    if previous_focus_subject == next_focus_subject:
        return

    event = focus_subject_memory_event(
        focus_subject=next_focus_subject,
        now=now,
    )
    recent_events = memory_repository.list_recent(limit=recent_limit)
    if any(
        item.content == event.content and item.source_context == "focus_subject"
        for item in recent_events
    ):
        return
    memory_repository.save_event(event)
