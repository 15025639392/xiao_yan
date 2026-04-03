from app.agent.autonomy import choose_next_action
from app.domain.models import BeingState, WakeMode


def test_awake_state_without_goal_prefers_reflection():
    state = BeingState(mode=WakeMode.AWAKE)
    action = choose_next_action(state=state, pending_goals=[], recent_events=[])
    assert action.kind == "reflect"
