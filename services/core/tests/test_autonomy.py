from datetime import datetime, timezone

from app.agent.autonomy import GoalFocusSummary, choose_next_action
from app.domain.models import BeingState, WakeMode


def test_awake_state_without_goal_prefers_reflection():
    state = BeingState(mode=WakeMode.AWAKE)
    action = choose_next_action(
        state=state,
        pending_goals=[],
        focus_summary=None,
        recent_events=[],
        cooldown_ready=True,
        now=datetime(2026, 4, 4, 10, 0, tzinfo=timezone.utc),
    )
    assert action.kind == "reflect"


def test_pending_goals_take_priority_over_reflection():
    state = BeingState(mode=WakeMode.AWAKE, active_goal_ids=["goal-1"])
    action = choose_next_action(
        state=state,
        pending_goals=state.active_goal_ids,
        focus_summary=None,
        recent_events=["用户刚问了一个问题"],
        cooldown_ready=True,
        now=datetime(2026, 4, 4, 10, 0, tzinfo=timezone.utc),
    )
    assert action.kind == "act"


def test_cooldown_blocks_immediate_follow_up():
    state = BeingState(mode=WakeMode.AWAKE)
    action = choose_next_action(
        state=state,
        pending_goals=[],
        focus_summary=None,
        recent_events=["用户刚问了一个问题"],
        cooldown_ready=False,
        now=datetime(2026, 4, 4, 10, 0, tzinfo=timezone.utc),
    )
    assert action.kind == "idle"


def test_late_chain_stage_prefers_consolidation_over_direct_action():
    state = BeingState(mode=WakeMode.AWAKE, active_goal_ids=["goal-1"])
    action = choose_next_action(
        state=state,
        pending_goals=state.active_goal_ids,
        focus_summary=GoalFocusSummary(
            goal_title="继续推进：整理今天的对话",
            chain_id="chain-1",
            chain_length=3,
            chain_generation=2,
            stage="consolidate",
        ),
        recent_events=[],
        cooldown_ready=True,
        now=datetime(2026, 4, 4, 10, 0, tzinfo=timezone.utc),
    )

    assert action.kind == "consolidate"
