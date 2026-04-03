from fastapi.testclient import TestClient

from app.main import app, get_memory_repository
from app.memory.models import MemoryEvent
from app.memory.repository import InMemoryMemoryRepository


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
