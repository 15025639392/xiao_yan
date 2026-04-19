from datetime import datetime, timezone

from app.agent.autonomy import FocusSummary, choose_next_action
from app.domain.models import BeingState, WakeMode


def test_awake_state_without_focus_prefers_reflection():
    state = BeingState(mode=WakeMode.AWAKE)
    action = choose_next_action(
        state=state,
        has_focus_subject=False,
        focus_summary=None,
        recent_events=[],
        cooldown_ready=True,
        now=datetime(2026, 4, 4, 10, 0, tzinfo=timezone.utc),
    )
    assert action.kind == "reflect"


def test_focus_subject_take_priority_over_reflection():
    state = BeingState(
        mode=WakeMode.AWAKE,
        focus_subject={
            "kind": "focus_trace",
            "title": "整理今天的对话记忆",
            "why_now": "这条线还挂在眼前。",
        },
    )
    action = choose_next_action(
        state=state,
        has_focus_subject=True,
        focus_summary=None,
        recent_events=["用户刚问了一个问题"],
        cooldown_ready=True,
        now=datetime(2026, 4, 4, 10, 0, tzinfo=timezone.utc),
    )
    assert action.kind == "act"


def test_focus_requires_explicit_focus_subject():
    state = BeingState(mode=WakeMode.AWAKE)
    action = choose_next_action(
        state=state,
        has_focus_subject=False,
        focus_summary=None,
        recent_events=["用户刚问了一个问题"],
        cooldown_ready=True,
        now=datetime(2026, 4, 4, 10, 0, tzinfo=timezone.utc),
    )
    assert action.kind == "reflect"


def test_cooldown_blocks_immediate_follow_up():
    state = BeingState(mode=WakeMode.AWAKE)
    action = choose_next_action(
        state=state,
        has_focus_subject=False,
        focus_summary=None,
        recent_events=["用户刚问了一个问题"],
        cooldown_ready=False,
        now=datetime(2026, 4, 4, 10, 0, tzinfo=timezone.utc),
    )
    assert action.kind == "idle"


def test_focus_subject_without_legacy_planner_can_still_drive_action():
    state = BeingState(
        mode=WakeMode.AWAKE,
        focus_subject={
            "kind": "lingering",
            "title": "你刚才说最近提不起劲",
            "why_now": "这句话还挂在心里。",
        },
    )
    action = choose_next_action(
        state=state,
        has_focus_subject=False,
        focus_summary=None,
        recent_events=["你刚才说最近提不起劲"],
        cooldown_ready=True,
        now=datetime(2026, 4, 4, 10, 0, tzinfo=timezone.utc),
    )
    assert action.kind == "act"


def test_late_chain_stage_prefers_consolidation_over_direct_action():
    state = BeingState(
        mode=WakeMode.AWAKE,
        focus_subject={
            "kind": "focus_trace",
            "title": "继续推进：整理今天的对话",
            "why_now": "这条线已经推到收束阶段。",
        },
    )
    action = choose_next_action(
        state=state,
        has_focus_subject=True,
        focus_summary=FocusSummary(
            focus_title="继续推进：整理今天的对话",
            stage="consolidate",
        ),
        recent_events=[],
        cooldown_ready=True,
        now=datetime(2026, 4, 4, 10, 0, tzinfo=timezone.utc),
    )

    assert action.kind == "consolidate"
