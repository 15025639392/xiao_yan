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
    assert state.focus_stage == "start"
    assert state.focus_step == 1


def test_world_state_for_late_chain_goal_enters_consolidation_stage():
    service = WorldStateService()

    state = service.bootstrap(
        being_state=BeingState(mode=WakeMode.AWAKE, active_goal_ids=["goal-1"]),
        focused_goals=[
            Goal(
                title="继续推进：继续推进：整理今天的对话记忆",
                status=GoalStatus.ACTIVE,
                chain_id="chain-1",
                generation=2,
            )
        ],
        now=datetime(2026, 4, 4, 14, 0),
    )

    assert state.energy == "high"
    assert state.mood == "calm"
    assert state.focus_tension == "medium"
    assert state.focus_stage == "consolidate"
    assert state.focus_step == 3


def test_world_state_prefers_first_focused_goal_for_stage_alignment():
    service = WorldStateService()

    state = service.bootstrap(
        being_state=BeingState(mode=WakeMode.AWAKE, active_goal_ids=["goal-1", "goal-2"]),
        focused_goals=[
            Goal(
                id="goal-1",
                title="整理今天的对话记忆",
                status=GoalStatus.ACTIVE,
                generation=0,
            ),
            Goal(
                id="goal-2",
                title="继续推进：继续推进：夜空观察",
                status=GoalStatus.ACTIVE,
                chain_id="chain-1",
                generation=2,
            ),
        ],
        now=datetime(2026, 4, 4, 14, 0),
    )

    assert state.focus_stage == "start"
    assert state.focus_step == 1


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


def test_world_service_builds_tired_night_event_with_goal_context():
    service = WorldStateService()
    world_state = service.bootstrap(
        being_state=BeingState(mode=WakeMode.AWAKE, active_goal_ids=["goal-1"]),
        focused_goals=[Goal(title="整理今天的对话记忆", status=GoalStatus.ACTIVE)],
        now=datetime(2026, 4, 4, 23, 0),
    )

    event = service.build_event(world_state, goal_title="整理今天的对话记忆")

    assert "夜里" in event
    assert "有点困" in event
    assert "整理今天的对话记忆" in event


def test_world_service_builds_consolidation_event_with_chain_context():
    service = WorldStateService()
    world_state = service.bootstrap(
        being_state=BeingState(mode=WakeMode.AWAKE, active_goal_ids=["goal-1"]),
        focused_goals=[
            Goal(
                title="继续推进：继续推进：整理今天的对话记忆",
                status=GoalStatus.ACTIVE,
                chain_id="chain-1",
                generation=2,
            )
        ],
        now=datetime(2026, 4, 4, 14, 0),
    )

    event = service.build_event(world_state, goal_title="继续推进：继续推进：整理今天的对话记忆")

    assert "第3步" in event
    assert "收束" in event


def test_world_service_builds_event_without_raw_goal_id_fallback():
    service = WorldStateService()
    world_state = service.bootstrap(
        being_state=BeingState(mode=WakeMode.AWAKE, active_goal_ids=["5ee3f6bedd0543ee9b6e368e24214d09"]),
        focused_goals=[],
        now=datetime(2026, 4, 4, 14, 0),
    )

    event = service.build_event(world_state, goal_title=None)

    assert "5ee3f6bedd0543ee9b6e368e24214d09" not in event
    assert "惦记着" not in event
