from app.domain.models import WakeMode
from app.usecases.lifecycle import go_to_sleep, wake_up


def test_wake_up_transitions_state_and_generates_brief():
    state = wake_up()
    assert state.mode == WakeMode.AWAKE
    assert state.current_thought is not None


def test_go_to_sleep_transitions_state():
    state = go_to_sleep()
    assert state.mode == WakeMode.SLEEPING
