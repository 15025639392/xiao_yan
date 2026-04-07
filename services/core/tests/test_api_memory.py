from fastapi.testclient import TestClient

from app.main import app, get_memory_service
from app.memory.models import MemoryKind
from app.memory.repository import InMemoryMemoryRepository
from app.memory.service import MemoryService


def test_get_relationship_summary_endpoint_returns_grouped_state():
    repository = InMemoryMemoryRepository()
    memory_service = MemoryService(repository=repository)
    memory_service.create(
        MemoryKind.FACT,
        "用户边界：你别催我，我希望先自己想一想再决定",
        importance=9,
        subject="用户边界",
        source_context="value_signal:boundary",
    )
    memory_service.create(
        MemoryKind.FACT,
        "承诺/计划：答应你明天提醒你复盘",
        importance=8,
        subject="对用户承诺",
        source_context="value_signal:commitment",
    )
    memory_service.create(
        MemoryKind.SEMANTIC,
        "用户偏好：喜欢先看方案再做决定",
        importance=7,
        subject="用户偏好",
    )

    def override_memory_service():
        return memory_service

    app.dependency_overrides[get_memory_service] = override_memory_service

    try:
        client = TestClient(app)
        response = client.get("/memory/relationship-summary")
        body = response.json()

        assert response.status_code == 200
        assert body["available"] is True
        assert any("别催我" in item for item in body["boundaries"])
        assert any("提醒你复盘" in item for item in body["commitments"])
        assert any("先看方案" in item for item in body["preferences"])
    finally:
        app.dependency_overrides.clear()


def test_get_memory_summary_endpoint_includes_relationship_summary():
    repository = InMemoryMemoryRepository()
    memory_service = MemoryService(repository=repository)
    memory_service.create(
        MemoryKind.FACT,
        "用户边界：你别催我，我希望先自己想一想再决定",
        importance=9,
        subject="用户边界",
        source_context="value_signal:boundary",
    )

    def override_memory_service():
        return memory_service

    app.dependency_overrides[get_memory_service] = override_memory_service

    try:
        client = TestClient(app)
        response = client.get("/memory/summary")
        body = response.json()

        assert response.status_code == 200
        assert body["relationship"]["available"] is True
        assert any("别催我" in item for item in body["relationship"]["boundaries"])
    finally:
        app.dependency_overrides.clear()
