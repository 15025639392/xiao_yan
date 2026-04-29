from __future__ import annotations

from datetime import datetime, timedelta

from app.domain.models import BeingState, WakeMode
from app.world.models import WorldState

_FOCUS_DEEPEN_AFTER = timedelta(seconds=20)
_FOCUS_CONSOLIDATE_AFTER = timedelta(seconds=60)


def time_of_day(hour: int) -> str:
    if hour < 6 or hour >= 22:
        return "night"
    if hour < 12:
        return "morning"
    if hour < 18:
        return "afternoon"
    return "evening"


def energy_for(time_of_day_value: str, state: BeingState) -> str:
    if state.mode != WakeMode.AWAKE:
        return "low"

    if time_of_day_value in {"morning", "afternoon"}:
        return "high"
    if time_of_day_value == "evening":
        return "medium"
    return "low"


def mood_for(state: BeingState, energy: str, focus_stage: str) -> str:
    if state.mode != WakeMode.AWAKE:
        return "tired"

    if focus_stage == "consolidate":
        return "calm"
    if energy == "low":
        return "tired"
    if focus_stage in {"start", "deepen"}:
        return "engaged"
    return "calm"


def focus_tension_for(state: BeingState, focus_stage: str) -> str:
    if state.mode != WakeMode.AWAKE:
        return "low"

    if focus_stage == "consolidate":
        return "medium"
    if state.focus_subject is not None:
        return "medium"
    return "low"


def event_lead(world_state: WorldState) -> str:
    if world_state.focus_stage == "consolidate" and world_state.focus_step is not None:
        return f"我想先把第{world_state.focus_step}步慢慢收束一下，"
    if world_state.time_of_day == "night" and world_state.mood == "tired":
        return "夜里很安静，我有点困，但"
    if world_state.mood == "calm":
        return "周围安静下来了，我心里也松一点了，"
    if world_state.focus_tension == "high":
        return "我还在留意眼前这件事，"
    if world_state.energy == "high":
        return "现在状态很清醒，"
    return "我在感受这一刻的变化，"


def focus_stage_for(state: BeingState, now: datetime | None = None) -> tuple[str, int | None]:
    if state.focus_subject is None:
        return "none", None
    if state.focus_effort is None:
        return "start", 1

    if state.focus_effort.action_kind == "consolidate":
        return "consolidate", 3

    current_time = now or datetime.now(tz=state.focus_effort.created_at.tzinfo)
    focus_age = _elapsed_since(state.focus_effort.created_at, current_time)
    if focus_age >= _FOCUS_CONSOLIDATE_AFTER:
        return "consolidate", 3
    if focus_age >= _FOCUS_DEEPEN_AFTER:
        return "deepen", 2
    return "start", 1


def _elapsed_since(start: datetime, end: datetime) -> timedelta:
    if start.tzinfo is None and end.tzinfo is not None:
        end = end.replace(tzinfo=None)
    elif start.tzinfo is not None and end.tzinfo is None:
        start = start.replace(tzinfo=None)
    return max(timedelta(0), end - start)


__all__ = [
    "time_of_day",
    "energy_for",
    "mood_for",
    "focus_tension_for",
    "event_lead",
    "focus_stage_for",
]
