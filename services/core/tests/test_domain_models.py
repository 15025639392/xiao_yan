from app.domain.models import BeingState, WakeMode


def test_default_being_state_is_sleeping():
    state = BeingState.default()
    assert state.mode == WakeMode.SLEEPING
    assert state.current_thought is None
    assert state.active_goal_ids == []
