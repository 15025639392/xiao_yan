from datetime import datetime

from app.domain.models import BeingState, WakeMode
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


def test_world_state_for_awake_focus_subject_is_engaged_and_medium_tension():
    service = WorldStateService()

    state = service.bootstrap(
        being_state=BeingState(
            mode=WakeMode.AWAKE,
            focus_subject={
                "kind": "focus_trace",
                "title": "整理今天的对话记忆",
                "why_now": "这条线还在继续。",
            },
        ),
        now=datetime(2026, 4, 4, 14, 0),
    )

    assert state.time_of_day == "afternoon"
    assert state.energy == "high"
    assert state.mood == "engaged"
    assert state.focus_tension == "medium"
    assert state.focus_stage == "start"
    assert state.focus_step == 1


def test_world_state_for_awake_without_focus_stays_calm():
    service = WorldStateService()

    state = service.bootstrap(
        being_state=BeingState(mode=WakeMode.AWAKE),
        now=datetime(2026, 4, 4, 14, 0),
    )

    assert state.energy == "high"
    assert state.mood == "calm"
    assert state.focus_tension == "low"


def test_world_state_uses_focus_subject_as_starting_focus():
    service = WorldStateService()

    state = service.bootstrap(
        being_state=BeingState(
            mode=WakeMode.AWAKE,
            focus_subject={
                "kind": "lingering",
                "title": "你刚才说最近提不起劲",
                "why_now": "这句话还挂在心里。",
            },
        ),
        now=datetime(2026, 4, 4, 14, 0),
    )

    assert state.energy == "high"
    assert state.mood == "engaged"
    assert state.focus_tension == "medium"
    assert state.focus_stage == "start"
    assert state.focus_step == 1


def test_world_service_builds_tired_night_event_with_focus_context():
    service = WorldStateService()
    world_state = service.bootstrap(
        being_state=BeingState(
            mode=WakeMode.AWAKE,
            focus_subject={
                "kind": "focus_trace",
                "title": "整理今天的对话记忆",
                "why_now": "夜里还是惦记着这件事。",
            },
        ),
        now=datetime(2026, 4, 4, 23, 0),
    )

    event = service.build_event(world_state, focus_title="整理今天的对话记忆")

    assert "夜里" in event
    assert "有点困" in event
    assert "整理今天的对话记忆" in event


def test_world_service_builds_event_without_raw_focus_id_fallback():
    service = WorldStateService()
    world_state = service.bootstrap(
        being_state=BeingState(mode=WakeMode.AWAKE),
        now=datetime(2026, 4, 4, 14, 0),
    )

    event = service.build_event(world_state, focus_title=None)

    assert "5ee3f6bedd0543ee9b6e368e24214d09" not in event
    assert "惦记着" not in event


def test_world_state_without_focus_subject_has_no_current_focus():
    service = WorldStateService()

    state = service.bootstrap(
        being_state=BeingState(mode=WakeMode.AWAKE),
        now=datetime(2026, 4, 4, 14, 0),
    )

    assert state.mood == "calm"
    assert state.focus_tension == "low"
    assert state.focus_stage == "none"
    assert state.focus_step is None
