from __future__ import annotations

from datetime import datetime
from typing import Any

from app.agent.loop_helpers import (
    build_chain_consolidation,
    build_focus_thought,
)
from app.domain.models import FocusMode, FocusSubject
from app.focus.effort import (
    command_effort,
    consolidate_effort,
    focus_hold_effort,
)
from app.memory.models import MemoryEntry, MemoryEvent, MemoryKind


def focus_subject_user_topic(
    *,
    title: str,
    why_now: str,
    source_ref: str | None,
) -> FocusSubject:
    return FocusSubject(
        kind="user_topic",
        title=title[:24],
        why_now=why_now,
        source_ref=source_ref,
    )


def focus_subject_lingering(
    *,
    title: str,
    why_now: str,
    source_ref: str | None,
) -> FocusSubject:
    return FocusSubject(
        kind="lingering",
        title=title,
        why_now=why_now,
        source_ref=source_ref,
    )


def focus_subject_memory_event(
    *,
    focus_subject: FocusSubject,
    now: datetime,
) -> MemoryEvent:
    entry = MemoryEntry.create(
        kind=MemoryKind.EPISODIC,
        content=f"当前牵挂转到“{focus_subject.title}”：{focus_subject.why_now}",
        source_context="focus_subject",
    ).model_copy(update={"created_at": now})
    event = MemoryEvent.from_entry(entry)
    return event.model_copy(update={"visibility": "user"})


def focus_command_update(
    *,
    focus_title: str,
    action_summary: str,
    result: Any,
    now: datetime,
) -> dict[str, object]:
    return {
        "current_thought": action_summary,
        "focus_effort": command_effort(
            focus_title=focus_title,
            command=result.command,
            output=result.output,
            now=now,
        ),
        "last_action": result,
    }


def focus_hold_update(
    *,
    focus_title: str,
    world_state,
    chain_progress: str | None,
    now: datetime,
) -> dict[str, object]:
    return {
        "current_thought": build_focus_thought(focus_title, now, world_state, chain_progress),
        "focus_effort": focus_hold_effort(
            focus_title=focus_title,
            now=now,
        ),
    }


def focus_consolidate_update(
    *,
    focus_title: str,
    world_state,
    chain_progress: str | None,
    now: datetime,
) -> dict[str, object]:
    return {
        "current_thought": build_chain_consolidation(
            focus_title,
            now,
            world_state,
            chain_progress,
        ),
        "focus_effort": consolidate_effort(
            focus_title=focus_title,
            now=now,
        ),
    }


def dropped_focus_update(
    *,
    focus_mode: FocusMode,
    focus_subject: FocusSubject | None,
) -> dict[str, object]:
    return {
        "focus_subject": focus_subject,
        "focus_effort": None,
        "focus_mode": focus_mode,
    }
