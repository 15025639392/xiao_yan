from datetime import datetime

from app.domain.models import BeingState
from app.goals.models import Goal
from app.utils.local_time import get_local_now
from app.world.models import WorldState
from app.world.world_rules import (
    energy_for as _energy_for,
    event_lead as _event_lead,
    focus_stage_for as _focus_stage_for,
    focus_tension_for as _focus_tension_for,
    mood_for as _mood_for,
    time_of_day as _time_of_day,
)


class WorldStateService:
    def bootstrap(
        self,
        being_state: BeingState | None = None,
        focused_goals: list[Goal] | None = None,
        now: datetime | None = None,
        latest_event: str | None = None,
        latest_event_at: datetime | None = None,
    ) -> WorldState:
        current_time = now or get_local_now()
        state = being_state or BeingState.default()
        goals = focused_goals or []
        focus_stage, focus_step = _focus_stage_for(goals)
        time_of_day = _time_of_day(current_time.hour)
        energy = _energy_for(time_of_day, state)
        mood = _mood_for(state, goals, energy, focus_stage)
        focus_tension = _focus_tension_for(state, goals, focus_stage)

        return WorldState(
            time_of_day=time_of_day,
            energy=energy,
            mood=mood,
            focus_tension=focus_tension,
            focus_stage=focus_stage,
            focus_step=focus_step,
            latest_event=latest_event,
            latest_event_at=latest_event_at,
        )

    def build_event(self, world_state: WorldState, goal_title: str | None = None) -> str:
        lead = _event_lead(world_state)
        if goal_title:
            return f"{lead}我还惦记着“{goal_title}”。"
        return lead
