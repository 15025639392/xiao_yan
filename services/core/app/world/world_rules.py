from __future__ import annotations

from app.domain.models import BeingState, WakeMode
from app.goals.models import Goal, GoalStatus
from app.world.models import WorldState


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


def mood_for(state: BeingState, goals: list[Goal], energy: str, focus_stage: str) -> str:
    if state.mode != WakeMode.AWAKE:
        return "tired"

    statuses = {goal.status for goal in goals}
    if GoalStatus.COMPLETED in statuses:
        return "calm"
    if focus_stage == "consolidate":
        return "calm"
    if energy == "low":
        return "tired"
    if GoalStatus.ACTIVE in statuses:
        return "engaged"
    return "calm"


def focus_tension_for(state: BeingState, goals: list[Goal], focus_stage: str) -> str:
    if state.mode != WakeMode.AWAKE:
        return "low"

    statuses = {goal.status for goal in goals}
    if focus_stage == "consolidate":
        return "medium"
    if GoalStatus.ACTIVE in statuses:
        return "high"
    if GoalStatus.COMPLETED in statuses or GoalStatus.ABANDONED in statuses:
        return "low"
    if state.active_goal_ids:
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


def focus_stage_for(goals: list[Goal]) -> tuple[str, int | None]:
    if not goals:
        return "none", None

    current_goal = goals[0]
    step = current_goal.generation + 1
    if current_goal.generation >= 2:
        return "consolidate", step
    if current_goal.generation == 1:
        return "deepen", step
    return "start", step


__all__ = [
    "time_of_day",
    "energy_for",
    "mood_for",
    "focus_tension_for",
    "event_lead",
    "focus_stage_for",
]
