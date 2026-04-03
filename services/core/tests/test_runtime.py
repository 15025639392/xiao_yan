from app.memory.models import MemoryEvent
from app.memory.repository import InMemoryMemoryRepository
from app.domain.models import WakeMode
from app.runtime import StateStore


def test_state_store_defaults_to_sleeping():
    store = StateStore()

    assert store.get().mode == WakeMode.SLEEPING


def test_state_store_persists_latest_state():
    store = StateStore()

    updated = store.wake()
    assert updated.mode == WakeMode.AWAKE

    sleeping = store.sleep()
    assert sleeping.mode == WakeMode.SLEEPING
    assert store.get().mode == WakeMode.SLEEPING


def test_state_store_wake_reflects_recent_autobio_memory():
    memory_repository = InMemoryMemoryRepository()
    memory_repository.save_event(
        MemoryEvent(
            kind="autobio",
            content="我最近像是一路从第1步走到第3步，开始学着把这些变化连成自己的经历。",
        )
    )
    store = StateStore(memory_repository=memory_repository)

    updated = store.wake()

    assert updated.mode == WakeMode.AWAKE
    assert updated.current_thought is not None
    assert "第1步走到第3步" in updated.current_thought


def test_state_store_wake_prefers_latest_autobio_memory():
    memory_repository = InMemoryMemoryRepository()
    memory_repository.save_event(
        MemoryEvent(kind="autobio", content="较早的回顾：第1步到第2步。")
    )
    memory_repository.save_event(
        MemoryEvent(kind="autobio", content="最新的回顾：第2步到第3步。")
    )
    store = StateStore(memory_repository=memory_repository)

    updated = store.wake()

    assert "最新的回顾" in updated.current_thought
    assert "较早的回顾" not in updated.current_thought
