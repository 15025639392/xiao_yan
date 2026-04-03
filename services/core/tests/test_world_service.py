from datetime import datetime

from app.domain.models import BeingState, WakeMode
from app.goals.models import Goal, GoalStatus
from app.world.service import WorldStateService


def test_world_state_bootstraps_daily_rhythm():
    service = WorldStateService()
    state = service.bootstrap()
    assert state.time_of_day in {"morning", "afternoon", "evening", "night"}


def test_world_state_for_sleeping_mode_is_low_energy_and_tired():
    service = WorldStateService()

    state = service.bootstrap(
        being_state=BeingState(mode=WakeMode.SLEEPING),
        now=datetime(2026, 4, 4, 23, 0),
    )

    assert state.time_of_day == "night"
    assert state.energy == "low"
    assert state.mood == "tired"
    assert state.focus_tension == "low"


def test_world_state_for_awake_active_goal_is_engaged_and_high_tension():
    service = WorldStateService()

    state = service.bootstrap(
        being_state=BeingState(mode=WakeMode.AWAKE, active_goal_ids=["goal-1"]),
        focused_goals=[Goal(title="整理今天的对话记忆", status=GoalStatus.ACTIVE)],
        now=datetime(2026, 4, 4, 14, 0),
    )

    assert state.time_of_day == "afternoon"
    assert state.energy == "high"
    assert state.mood == "engaged"
    assert state.focus_tension == "high"


def test_world_state_for_completed_focus_becomes_calm():
    service = WorldStateService()

    state = service.bootstrap(
        being_state=BeingState(mode=WakeMode.AWAKE, active_goal_ids=["goal-1"]),
        focused_goals=[Goal(title="整理今天的对话记忆", status=GoalStatus.COMPLETED)],
        now=datetime(2026, 4, 4, 14, 0),
    )

    assert state.energy == "high"
    assert state.mood == "calm"
    assert state.focus_tension == "low"
