from fastapi.testclient import TestClient

from app.api.deps import get_memory_repository, get_mempalace_adapter, get_state_store
from app.domain.models import BeingState, FocusMode, WakeMode
from app.main import app
from app.memory.repository import InMemoryMemoryRepository
from app.runtime import StateStore


def test_get_state_returns_current_runtime_state():
    client = TestClient(app)

    wake_response = client.post("/lifecycle/wake")
    assert wake_response.status_code == 200

    response = client.get("/state")

    assert response.status_code == 200
    assert response.json()["mode"] == "awake"
    assert response.json()["focus_mode"] == "autonomy"
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


def test_get_state_does_not_auto_derive_focus_context_without_focus_subject():
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
        assert body["focus_context"] is None
    finally:
        app.dependency_overrides.clear()


def test_get_state_includes_focus_subject_driven_context():
    state_store = StateStore(
        BeingState(
            mode=WakeMode.AWAKE,
            focus_subject={
                "kind": "lingering",
                "title": "你刚才说最近提不起劲",
                "why_now": "这句话虽然还没整理成目标，但我心里还挂着。",
                "source_ref": "我最近挺累的，感觉做什么都提不起劲",
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
        assert body["focus_subject"]["kind"] == "lingering"
        assert body["focus_context"]["focus_title"] == "你刚才说最近提不起劲"
        assert body["focus_context"]["source_kind"] == "lingering_focus"
        assert "我心里还挂着" in body["focus_context"]["reason_label"]
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
        assert payload["chat_memory"]["palace_path"] == "/tmp/palace"
    finally:
        app.dependency_overrides.clear()
