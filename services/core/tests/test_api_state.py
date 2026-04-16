from fastapi.testclient import TestClient

from app.api.deps import get_mempalace_adapter
from app.domain.models import BeingState, FocusMode, WakeMode
from app.main import app, get_memory_repository, get_state_store
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


def test_get_state_downgrades_self_programming_focus_to_autonomy():
    state_store = StateStore(
        BeingState(
            mode=WakeMode.AWAKE,
            focus_mode=FocusMode.SELF_IMPROVEMENT,
            self_programming_job={
                "reason": "测试失败：状态面板没有展示自我编程状态。",
                "target_area": "ui",
                "status": "verifying",
                "spec": "补上自我编程状态展示。",
                "patch_summary": "已修改状态面板。",
                "verification": {
                    "commands": ["npm test -- --run src/components/StatusPanel.test.tsx"],
                    "passed": True,
                    "summary": "3 passed",
                },
            },
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
