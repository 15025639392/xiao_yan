from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.domain.models import BeingState, WakeMode
from app.main import app, get_memory_repository, get_state_store
from app.memory.models import MemoryEvent
from app.memory.repository import InMemoryMemoryRepository
from app.runtime import StateStore


def test_post_wake_returns_awake_state():
    client = TestClient(app)
    response = client.post("/lifecycle/wake")
    assert response.status_code == 200
    assert response.json()["mode"] == "awake"


def test_post_wake_uses_recent_autobio_for_first_thought():
    memory_repository = InMemoryMemoryRepository()
    memory_repository.save_event(
        MemoryEvent(
            kind="autobio",
            content="我最近像是一路从第1步走到第3步，开始学着把这些变化连成自己的经历。",
        )
    )

    def override_memory_repository():
        return memory_repository

    app.dependency_overrides[get_memory_repository] = override_memory_repository

    try:
        client = TestClient(app)
        response = client.post("/lifecycle/wake")
        assert response.status_code == 200
        assert "第1步走到第3步" in response.json()["current_thought"]
    finally:
        app.dependency_overrides.clear()


def test_post_wake_omits_removed_legacy_fields():
    state_store = StateStore(
        BeingState(
            mode=WakeMode.SLEEPING,
        )
    )

    def override_state_store():
        return state_store

    app.dependency_overrides[get_state_store] = override_state_store

    try:
        client = TestClient(app)
        response = client.post("/lifecycle/wake")
        assert response.status_code == 200
        body = response.json()
        assert body["mode"] == "awake"
        assert "self_programming_job" not in body
    finally:
        app.dependency_overrides.clear()


def test_post_wake_preserves_last_proactive_markers():
    marker_time = datetime(2026, 4, 5, 9, 0, tzinfo=timezone.utc)
    state_store = StateStore(
        BeingState(
            mode=WakeMode.SLEEPING,
            last_proactive_source="嗯我同意",
            last_proactive_at=marker_time,
        )
    )

    def override_state_store():
        return state_store

    app.dependency_overrides[get_state_store] = override_state_store

    try:
        client = TestClient(app)
        response = client.post("/lifecycle/wake")
        assert response.status_code == 200
        body = response.json()
        assert body["last_proactive_source"] == "嗯我同意"
        assert body["last_proactive_at"] == "2026-04-05T09:00:00Z"
    finally:
        app.dependency_overrides.clear()


def test_post_sleep_omits_removed_legacy_fields():
    state_store = StateStore(
        BeingState(
            mode=WakeMode.AWAKE,
        )
    )

    def override_state_store():
        return state_store

    app.dependency_overrides[get_state_store] = override_state_store

    try:
        client = TestClient(app)
        response = client.post("/lifecycle/sleep")
        assert response.status_code == 200
        body = response.json()
        assert body["mode"] == "sleeping"
        assert "self_programming_job" not in body
    finally:
        app.dependency_overrides.clear()


def test_options_wake_allows_cors_preflight():
    client = TestClient(app)
    response = client.options(
        "/lifecycle/wake",
        headers={
            "Origin": "http://127.0.0.1:5173",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:5173"
