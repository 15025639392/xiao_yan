from datetime import datetime

from app.domain.models import BeingState, WakeMode
from app.goals.models import Goal, GoalStatus
from app.world.models import WorldState


class WorldStateService:
    def bootstrap(
        self,
        being_state: BeingState | None = None,
        focused_goals: list[Goal] | None = None,
        now: datetime | None = None,
        latest_event: str | None = None,
        latest_event_at: datetime | None = None,
    ) -> WorldState:
        current_time = now or datetime.now()
        state = being_state or BeingState.default()
        goals = focused_goals or []
        time_of_day = _time_of_day(current_time.hour)
        energy = _energy_for(time_of_day, state)
        mood = _mood_for(state, goals, energy)
        focus_tension = _focus_tension_for(state, goals)

        return WorldState(
            time_of_day=time_of_day,
            energy=energy,
            mood=mood,
            focus_tension=focus_tension,
            latest_event=latest_event,
            latest_event_at=latest_event_at,
        )

    def build_event(self, world_state: WorldState, goal_title: str | None = None) -> str:
        lead = _event_lead(world_state)
        if goal_title:
            return f"{lead}我还惦记着“{goal_title}”。"
        return lead


def _time_of_day(hour: int) -> str:
    if hour < 6 or hour >= 22:
        return "night"
    if hour < 12:
        return "morning"
    if hour < 18:
        return "afternoon"
    return "evening"


def _energy_for(time_of_day: str, state: BeingState) -> str:
    if state.mode != WakeMode.AWAKE:
        return "low"

    if time_of_day in {"morning", "afternoon"}:
        return "high"
    if time_of_day == "evening":
        return "medium"
    return "low"


def _mood_for(state: BeingState, goals: list[Goal], energy: str) -> str:
    if state.mode != WakeMode.AWAKE:
        return "tired"

    statuses = {goal.status for goal in goals}
    if GoalStatus.COMPLETED in statuses:
        return "calm"
    if energy == "low":
        return "tired"
    if GoalStatus.ACTIVE in statuses:
        return "engaged"
    return "calm"


def _focus_tension_for(state: BeingState, goals: list[Goal]) -> str:
    if state.mode != WakeMode.AWAKE:
        return "low"

    statuses = {goal.status for goal in goals}
    if GoalStatus.ACTIVE in statuses:
        return "high"
    if GoalStatus.COMPLETED in statuses or GoalStatus.ABANDONED in statuses:
        return "low"
    if state.active_goal_ids:
        return "medium"
    return "low"


def _event_lead(world_state: WorldState) -> str:
    if world_state.time_of_day == "night" and world_state.mood == "tired":
        return "夜里很安静，我有点困，但"
    if world_state.mood == "calm":
        return "周围安静下来了，我心里也松一点了，"
    if world_state.focus_tension == "high":
        return "我还在留意眼前这件事，"
    if world_state.energy == "high":
        return "现在状态很清醒，"
    return "我在感受这一刻的变化，"
