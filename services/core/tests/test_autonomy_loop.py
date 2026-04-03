from app.agent.loop import AutonomyLoop
from app.domain.models import BeingState, WakeMode
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
