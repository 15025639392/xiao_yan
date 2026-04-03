from datetime import datetime, timedelta, timezone

from app.agent.loop import AutonomyLoop
from app.domain.models import BeingState, WakeMode
from app.goals.repository import InMemoryGoalRepository
from app.memory.models import MemoryEvent
from app.memory.repository import InMemoryMemoryRepository
from app.runtime import StateStore


def test_tick_once_keeps_sleeping_state_unchanged():
    store = StateStore()
    repo = InMemoryMemoryRepository()
    loop = AutonomyLoop(store, repo)

    state = loop.tick_once()

    assert state.mode == WakeMode.SLEEPING
    assert state.current_thought is None


def test_tick_once_updates_awake_state_with_proactive_thought():
    store = StateStore(BeingState(mode=WakeMode.AWAKE))
    repo = InMemoryMemoryRepository()
    repo.save_event(MemoryEvent(kind="chat", role="user", content="你喜欢星星吗"))
    loop = AutonomyLoop(store, repo)

    state = loop.tick_once()

    assert state.mode == WakeMode.AWAKE
    assert state.current_thought is not None
    assert "星星" in state.current_thought


def test_tick_once_adds_one_proactive_assistant_message_for_latest_user_message():
    store = StateStore(BeingState(mode=WakeMode.AWAKE))
    repo = InMemoryMemoryRepository()
    repo.save_event(MemoryEvent(kind="chat", role="user", content="你还记得星星吗"))
    loop = AutonomyLoop(store, repo)

    first_state = loop.tick_once()
    recent_after_first_tick = list(reversed(repo.list_recent(limit=5)))

    second_state = loop.tick_once()
    recent_after_second_tick = list(reversed(repo.list_recent(limit=5)))

    assert first_state.last_proactive_source == "你还记得星星吗"
    assert second_state.last_proactive_source == "你还记得星星吗"
    assert [event.role for event in recent_after_first_tick] == ["user", "assistant"]
    assert [event.role for event in recent_after_second_tick] == ["user", "assistant"]
    assert "星星" in recent_after_first_tick[-1].content


def test_tick_once_respects_proactive_cooldown():
    now = datetime(2026, 4, 4, 10, 0, tzinfo=timezone.utc)
    store = StateStore(
        BeingState(
            mode=WakeMode.AWAKE,
            last_proactive_source="之前的话题",
            last_proactive_at=now - timedelta(seconds=20),
        )
    )
    repo = InMemoryMemoryRepository()
    repo.save_event(MemoryEvent(kind="chat", role="user", content="你现在在想什么"))
    loop = AutonomyLoop(store, repo, now_provider=lambda: now)

    state = loop.tick_once()
    recent = list(reversed(repo.list_recent(limit=5)))

    assert state.current_thought is None
    assert [event.role for event in recent] == ["user"]


def test_tick_once_generates_time_aware_proactive_message():
    now = datetime(2026, 4, 4, 22, 0, tzinfo=timezone.utc)
    store = StateStore(BeingState(mode=WakeMode.AWAKE))
    repo = InMemoryMemoryRepository()
    repo.save_event(MemoryEvent(kind="chat", role="user", content="你喜欢夜空吗"))
    loop = AutonomyLoop(store, repo, now_provider=lambda: now)

    state = loop.tick_once()

    assert state.current_thought is not None
    assert "晚上" in state.current_thought


def test_tick_once_surfaces_pending_goal_as_current_focus():
    now = datetime(2026, 4, 4, 14, 0, tzinfo=timezone.utc)
    store = StateStore(
        BeingState(mode=WakeMode.AWAKE, active_goal_ids=["整理今天的对话记忆"])
    )
    repo = InMemoryMemoryRepository()
    goals = InMemoryGoalRepository()
    loop = AutonomyLoop(store, repo, goals, now_provider=lambda: now)

    state = loop.tick_once()

    assert state.current_thought is not None
    assert "整理今天的对话记忆" in state.current_thought


def test_tick_once_generates_goal_from_latest_user_topic_when_no_active_goals():
    now = datetime(2026, 4, 4, 14, 0, tzinfo=timezone.utc)
    store = StateStore(BeingState(mode=WakeMode.AWAKE))
    repo = InMemoryMemoryRepository()
    repo.save_event(MemoryEvent(kind="chat", role="user", content="最近总在想星星和夜空"))
    goals = InMemoryGoalRepository()
    loop = AutonomyLoop(store, repo, goals, now_provider=lambda: now)

    state = loop.tick_once()
    active_goals = goals.list_active_goals()

    assert len(active_goals) == 1
    assert "星星和夜空" in active_goals[0].title
    assert state.active_goal_ids == [active_goals[0].id]
    assert "星星和夜空" in state.current_thought
