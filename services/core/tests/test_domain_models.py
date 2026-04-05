from app.domain.models import BeingState, FocusMode, WakeMode


def test_default_being_state_is_sleeping():
    state = BeingState.default()
    assert state.mode == WakeMode.SLEEPING
    assert state.focus_mode == FocusMode.SLEEPING
    assert state.current_thought is None
    assert state.active_goal_ids == []
    assert state.today_plan is None
    assert state.last_action is None
    assert state.self_improvement_job is None


def test_focus_mode_supports_self_improvement():
    state = BeingState(mode=WakeMode.AWAKE, focus_mode=FocusMode.SELF_IMPROVEMENT)

    assert state.focus_mode == FocusMode.SELF_IMPROVEMENT
