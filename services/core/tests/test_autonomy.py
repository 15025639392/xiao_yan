from datetime import datetime, timedelta, timezone

from app.agent.autonomy import FocusSummary, choose_next_action
from app.agent.loop import AutonomyLoop
from app.agent.xhs_workflow_engine import XhsWorkDomainAction
from app.domain.models import BeingState, WakeMode, XhsWorkDomainState, XhsWorkStatus
from app.focus.effort import focus_hold_effort
from app.memory.models import MemoryEvent
from app.memory.repository import InMemoryMemoryRepository
from app.runtime import StateStore
from app.world.models import WorldState


class _StubVisibleChatRuntime:
    def __init__(self) -> None:
        self.assistant_messages: list[tuple[str, str | None, str | None]] = []

    def record_assistant_message(
        self,
        assistant_response: str,
        assistant_session_id: str | None = None,
        request_key: str | None = None,
    ) -> bool:
        self.assistant_messages.append((assistant_response, assistant_session_id, request_key))
        return True


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


def test_autonomy_loop_records_proactive_message_to_visible_chat_runtime():
    now = datetime(2026, 4, 4, 10, 0, tzinfo=timezone.utc)
    repository = InMemoryMemoryRepository()
    repository.save_event(MemoryEvent(kind="chat", role="user", content="昨晚说到星星"))
    state_store = StateStore(BeingState(mode=WakeMode.AWAKE), memory_repository=repository)
    visible_chat = _StubVisibleChatRuntime()
    loop = AutonomyLoop(
        state_store,
        repository,
        now_provider=lambda: now,
        chat_memory_runtime=visible_chat,
    )

    loop.tick_once()

    assert len(visible_chat.assistant_messages) == 1
    message, assistant_session_id, request_key = visible_chat.assistant_messages[0]
    assert "昨晚说到星星" in message
    assert assistant_session_id == "assistant_proactive_1775296800000"
    assert request_key == assistant_session_id


def test_autonomy_loop_consolidates_and_drops_stale_focus_subject():
    now = datetime(2026, 4, 4, 10, 2, tzinfo=timezone.utc)
    repository = InMemoryMemoryRepository()
    state_store = StateStore(
        BeingState(
            mode=WakeMode.AWAKE,
            focus_subject={
                "kind": "lingering",
                "title": "你刚才说最近提不起劲",
                "why_now": "这句话还挂在心里。",
            },
            focus_effort=focus_hold_effort(
                focus_title="你刚才说最近提不起劲",
                now=now - timedelta(seconds=61),
            ),
        ),
        memory_repository=repository,
    )
    loop = AutonomyLoop(
        state_store,
        repository,
        now_provider=lambda: now,
    )

    loop.tick_once()

    latest = state_store.get()
    assert latest.focus_subject is None
    assert latest.focus_effort is None
    assert latest.current_thought is not None
    assert "收束" in latest.current_thought


def test_autonomy_loop_does_not_refresh_focus_hold_age_forever():
    current_now = datetime(2026, 4, 4, 10, 0, tzinfo=timezone.utc)
    repository = InMemoryMemoryRepository()
    state_store = StateStore(
        BeingState(
            mode=WakeMode.AWAKE,
            focus_subject={
                "kind": "lingering",
                "title": "你刚才说最近提不起劲",
                "why_now": "这句话还挂在心里。",
            },
        ),
        memory_repository=repository,
    )
    loop = AutonomyLoop(
        state_store,
        repository,
        now_provider=lambda: current_now,
    )
    loop._maybe_generate_upgrade_proposal = lambda *args, **kwargs: None  # type: ignore[method-assign]
    loop.xhs_engine.tick = lambda: None  # type: ignore[method-assign]

    loop.tick_once()
    first_effort = state_store.get().focus_effort
    assert first_effort is not None
    assert first_effort.action_kind == "focus_hold"
    assert first_effort.created_at == current_now

    current_now = current_now + timedelta(seconds=30)
    loop.tick_once()
    assert state_store.get().focus_effort == first_effort

    current_now = current_now + timedelta(seconds=31)
    loop.tick_once()

    latest = state_store.get()
    assert latest.focus_subject is None
    assert latest.focus_effort is None


def test_inner_stage_memory_does_not_repeat_same_step():
    now = datetime(2026, 4, 4, 10, 0, tzinfo=timezone.utc)
    repository = InMemoryMemoryRepository()
    state_store = StateStore(
        BeingState(
            mode=WakeMode.AWAKE,
            focus_subject={
                "kind": "lingering",
                "title": "整理今天的对话记忆",
                "why_now": "这条线还挂在眼前。",
            },
        ),
        memory_repository=repository,
    )
    loop = AutonomyLoop(state_store, repository, now_provider=lambda: now)
    recent_events = [
        MemoryEvent(
            kind="inner",
            content="我感觉自己已经走到第1步，正在进入起步阶段，还在围绕“另一个焦点”。",
        )
    ]
    world_state = WorldState(
        time_of_day="morning",
        energy="high",
        mood="engaged",
        focus_tension="medium",
        focus_stage="start",
        focus_step=1,
    )

    loop._maybe_record_inner_stage_memory(state_store.get(), recent_events, world_state, now)

    assert repository.list_recent(limit=10) == []


def test_inner_stage_memory_records_new_step_after_recent_step():
    now = datetime(2026, 4, 4, 10, 0, tzinfo=timezone.utc)
    repository = InMemoryMemoryRepository()
    state_store = StateStore(
        BeingState(
            mode=WakeMode.AWAKE,
            focus_subject={
                "kind": "lingering",
                "title": "整理今天的对话记忆",
                "why_now": "这条线还挂在眼前。",
            },
        ),
        memory_repository=repository,
    )
    loop = AutonomyLoop(state_store, repository, now_provider=lambda: now)
    recent_events = [MemoryEvent(kind="inner", content="我感觉自己已经走到第1步。")]
    world_state = WorldState(
        time_of_day="morning",
        energy="high",
        mood="engaged",
        focus_tension="medium",
        focus_stage="deepen",
        focus_step=2,
    )

    loop._maybe_record_inner_stage_memory(state_store.get(), recent_events, world_state, now)

    recorded = repository.list_recent(limit=10)
    assert len(recorded) == 1
    assert recorded[0].kind == "inner"
    assert "第2步" in recorded[0].content


def test_autonomy_loop_clears_stale_xhs_focus_when_engine_is_waiting():
    now = datetime(2026, 4, 4, 10, 0, tzinfo=timezone.utc)
    repository = InMemoryMemoryRepository()
    state_store = StateStore(
        BeingState(
            mode=WakeMode.AWAKE,
            focus_subject={
                "kind": "xhs_workflow",
                "title": "已准备到发布前",
                "why_now": "小红书工作流: publishing",
            },
            xhs_work_domain=XhsWorkDomainState(
                state={
                    "status": XhsWorkStatus.REVIEWING,
                    "current_focus": "已上传并填好，停在发布前最后一步",
                    "review_session_id": "review-session",
                }
            ),
        ),
        memory_repository=repository,
    )
    loop = AutonomyLoop(state_store, repository, now_provider=lambda: now)
    loop.xhs_engine.tick = lambda: None  # type: ignore[method-assign]
    loop._maybe_generate_upgrade_proposal = lambda *args, **kwargs: None  # type: ignore[method-assign]

    loop.tick_once()

    latest = state_store.get()
    assert latest.focus_subject is None


def test_autonomy_loop_does_not_hold_xhs_focus_for_manual_review_action():
    now = datetime(2026, 4, 4, 10, 0, tzinfo=timezone.utc)
    repository = InMemoryMemoryRepository()
    state_store = StateStore(
        BeingState(
            mode=WakeMode.AWAKE,
            xhs_work_domain=XhsWorkDomainState(
                state={
                    "status": XhsWorkStatus.REVIEWING,
                    "current_focus": "已上传并填好，停在发布前最后一步",
                    "review_session_id": "review-session",
                }
            ),
        ),
        memory_repository=repository,
    )
    loop = AutonomyLoop(state_store, repository, now_provider=lambda: now)
    loop.xhs_engine.tick = lambda: XhsWorkDomainAction(
        kind="publishing",
        title="已准备到发布前",
        data={},
    )  # type: ignore[method-assign]
    loop._maybe_generate_upgrade_proposal = lambda *args, **kwargs: None  # type: ignore[method-assign]

    loop.tick_once()

    latest = state_store.get()
    assert latest.focus_subject is None
