from fastapi.testclient import TestClient

from app.api.deps import get_mempalace_adapter
from app.domain.models import BeingState, FocusMode, WakeMode
from app.goals.models import Goal
from app.goals.repository import InMemoryGoalRepository
from app.main import app, get_goal_repository, get_memory_repository, get_state_store
from app.memory.repository import InMemoryMemoryRepository
from app.runtime import StateStore


def test_get_state_returns_current_runtime_state():
    client = TestClient(app)

    wake_response = client.post("/lifecycle/wake")
    assert wake_response.status_code == 200

    response = client.get("/state")

    assert response.status_code == 200
    assert response.json()["mode"] == "awake"
    assert response.json()["focus_mode"] in {"autonomy", "morning_plan"}
    assert "self_programming_job" not in response.json()


def test_get_state_omits_removed_legacy_fields():
    state_store = StateStore(
        BeingState(
            mode=WakeMode.AWAKE,
            focus_mode=FocusMode.AUTONOMY,
        )
    )

    def override_state_store():
        return state_store

    app.dependency_overrides[get_state_store] = override_state_store

    try:
        client = TestClient(app)
        response = client.get("/state")
        body = response.json()

        assert response.status_code == 200
        assert body["focus_mode"] == "autonomy"
        assert "self_programming_job" not in body
    finally:
        app.dependency_overrides.clear()


def test_get_state_includes_focus_context_when_goal_is_active():
    goal_repository = InMemoryGoalRepository()
    goal = goal_repository.save_goal(Goal(id="goal-1", title="整理今天的对话记忆", source="你现在在忙什么"))
    state_store = StateStore(
        BeingState(
            mode=WakeMode.AWAKE,
            focus_mode=FocusMode.AUTONOMY,
            active_goal_ids=[goal.id],
        )
    )

    def override_state_store():
        return state_store

    def override_goal_repository():
        return goal_repository

    app.dependency_overrides[get_state_store] = override_state_store
    app.dependency_overrides[get_goal_repository] = override_goal_repository

    try:
        client = TestClient(app)
        response = client.get("/state")
        body = response.json()

        assert response.status_code == 200
        assert body["focus_context"]["goal_title"] == "整理今天的对话记忆"
        assert body["focus_context"]["source_kind"] == "retained_goal"
        assert body["focus_context"]["reason_kind"] == "goal_still_active"
        assert "还没完成" in body["focus_context"]["reason_label"]
    finally:
        app.dependency_overrides.clear()


def test_get_mac_console_environment_status_returns_bootstrap_snapshot():
    client = TestClient(app)

    response = client.get("/environment/mac-console")
    body = response.json()

    assert response.status_code == 200
    assert body["state"]
    assert isinstance(body["healthy"], bool)
    assert isinstance(body["platform"], str)
    assert isinstance(body["summary"], str)


def test_get_memory_backends_includes_mempalace_snapshot():
    class _StubMemPalaceAdapter:
        def status_snapshot(self) -> dict:
            return {
                "enabled": True,
                "palace_path": "/tmp/palace",
                "palace_exists": False,
                "dependency_available": True,
                "results_limit": 3,
                "wing": "wing_xiaoyan",
                "room": "chat_exchange",
            }

    memory_repository = InMemoryMemoryRepository()
    mempalace_adapter = _StubMemPalaceAdapter()

    def override_memory_repository():
        return memory_repository

    def override_mempalace_adapter():
        return mempalace_adapter

    app.dependency_overrides[get_memory_repository] = override_memory_repository
    app.dependency_overrides[get_mempalace_adapter] = override_mempalace_adapter

    try:
        client = TestClient(app)
        response = client.get("/memory/backends")
        assert response.status_code == 200
        payload = response.json()
        assert payload["chat_memory"]["enabled"] is True
        assert payload["chat_memory"]["palace_path"] == "/tmp/palace"
    finally:
        app.dependency_overrides.clear()
