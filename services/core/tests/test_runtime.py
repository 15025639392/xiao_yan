from pathlib import Path

from app.memory.models import MemoryEvent
from app.memory.repository import InMemoryMemoryRepository
from app.domain.models import FocusMode, WakeMode
from app.runtime import StateStore


def test_state_store_defaults_to_sleeping():
    store = StateStore()

    assert store.get().mode == WakeMode.SLEEPING
    assert store.get().focus_mode == FocusMode.SLEEPING


def test_state_store_persists_latest_state():
    store = StateStore()

    updated = store.wake()
    assert updated.mode == WakeMode.AWAKE
    assert updated.focus_mode == FocusMode.AUTONOMY

    sleeping = store.sleep()
    assert sleeping.mode == WakeMode.SLEEPING
    assert sleeping.focus_mode == FocusMode.SLEEPING
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


def test_state_store_persists_state_to_disk(tmp_path: Path):
    storage_path = tmp_path / "state.json"
    store = StateStore(storage_path=storage_path)

    updated = store.set(
        store.get().model_copy(
            update={
                "mode": WakeMode.AWAKE,
                "focus_mode": FocusMode.MORNING_PLAN,
                "current_thought": "今天先把轮廓理一下。",
                "active_goal_ids": ["goal-1"],
                "today_plan": {
                    "goal_id": "goal-1",
                    "goal_title": "整理今天的对话记忆",
                    "steps": [{"content": "把“整理今天的对话记忆”的轮廓理一下", "status": "pending"}],
                },
            }
        )
    )

    reloaded = StateStore(storage_path=storage_path)

    assert updated.focus_mode == FocusMode.MORNING_PLAN
    assert reloaded.get() == updated


def test_state_store_uses_persisted_state_as_initial_value(tmp_path: Path):
    storage_path = tmp_path / "state.json"
    seeded = StateStore(storage_path=storage_path)
    seeded.set(
        seeded.get().model_copy(
            update={
                "mode": WakeMode.AWAKE,
                "focus_mode": FocusMode.AUTONOMY,
                "current_thought": "我还惦记着今天的整理。",
            }
        )
    )

    reloaded = StateStore(
        initial_state=None,
        storage_path=storage_path,
    )

    assert reloaded.get().mode == WakeMode.AWAKE
    assert reloaded.get().focus_mode == FocusMode.AUTONOMY
    assert reloaded.get().current_thought == "我还惦记着今天的整理。"


def test_state_store_persists_self_improvement_job_to_disk(tmp_path: Path):
    storage_path = tmp_path / "state.json"
    store = StateStore(storage_path=storage_path)

    updated = store.set(
        store.get().model_copy(
            update={
                "mode": WakeMode.AWAKE,
                "focus_mode": FocusMode.SELF_IMPROVEMENT,
                "self_improvement_job": {
                    "reason": "连续多次没有有效推进",
                    "target_area": "agent",
                    "status": "verifying",
                    "spec": "提升自主循环对空转的处理",
                    "patch_summary": "新增自我编程状态切换",
                    "verification": {
                        "commands": ["pytest tests/test_autonomy_loop.py -q"],
                        "passed": True,
                        "summary": "1 passed",
                    },
                },
            }
        )
    )

    reloaded = StateStore(storage_path=storage_path)

    assert updated.focus_mode == FocusMode.SELF_IMPROVEMENT
    assert updated.self_improvement_job is not None
    assert updated.self_improvement_job.status == "verifying"
    assert reloaded.get() == updated
