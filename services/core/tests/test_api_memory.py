from fastapi.testclient import TestClient

from app.main import app, get_memory_service
from app.memory.models import MemoryEvent, MemoryKind
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


def test_memory_soft_delete_and_restore_contract():
    repository = InMemoryMemoryRepository()
    memory_service = MemoryService(repository=repository)

    def override_memory_service():
        return memory_service

    app.dependency_overrides[get_memory_service] = override_memory_service

    try:
        client = TestClient(app)
        create_response = client.post(
            "/memory",
            json={
                "kind": "fact",
                "content": "用户偏好结构化输出",
                "importance": 8,
            },
        )
        assert create_response.status_code == 200
        memory_id = create_response.json()["entry"]["id"]

        delete_response = client.delete(f"/memory/{memory_id}")
        assert delete_response.status_code == 200
        assert delete_response.json()["mode"] == "soft"

        active_timeline = client.get("/memory/timeline")
        assert active_timeline.status_code == 200
        assert all(entry["id"] != memory_id for entry in active_timeline.json()["entries"])

        deleted_timeline = client.get("/memory/timeline", params={"status": "deleted"})
        assert deleted_timeline.status_code == 200
        assert [entry["id"] for entry in deleted_timeline.json()["entries"]] == [memory_id]
        assert deleted_timeline.json()["entries"][0]["status"] == "deleted"

        restore_response = client.post(f"/memory/{memory_id}/restore")
        assert restore_response.status_code == 200

        restored_timeline = client.get("/memory/timeline")
        assert restored_timeline.status_code == 200
        assert [entry["id"] for entry in restored_timeline.json()["entries"]] == [memory_id]
        assert restored_timeline.json()["entries"][0]["status"] == "active"
    finally:
        app.dependency_overrides.clear()


def test_memory_timeline_filters_by_status_kind_namespace_and_visibility():
    repository = InMemoryMemoryRepository()
    memory_service = MemoryService(repository=repository)

    active_user_fact = MemoryEvent(
        kind="fact",
        content="用户希望先看方案再做决定",
        namespace="knowledge",
        visibility="user",
    )
    deleted_internal_fact = MemoryEvent(
        kind="fact",
        content="内部观察：最近更偏好短回复",
        namespace="knowledge",
        visibility="internal",
    )
    chat_event = MemoryEvent(
        kind="chat",
        role="user",
        content="我们继续",
        namespace="chat",
        visibility="user",
    )
    repository.save_event(active_user_fact)
    repository.save_event(deleted_internal_fact)
    repository.save_event(chat_event)
    assert repository.soft_delete_event(deleted_internal_fact.entry_id) is True

    def override_memory_service():
        return memory_service

    app.dependency_overrides[get_memory_service] = override_memory_service

    try:
        client = TestClient(app)
        filtered = client.get(
            "/memory/timeline",
            params={
                "status": "active",
                "kind": "fact",
                "namespace": "knowledge",
                "visibility": "user",
            },
        )
        assert filtered.status_code == 200
        body = filtered.json()
        assert [entry["id"] for entry in body["entries"]] == [active_user_fact.entry_id]
        assert body["entries"][0]["status"] == "active"

        deleted_only = client.get(
            "/memory/timeline",
            params={
                "status": "deleted",
                "namespace": "knowledge",
            },
        )
        assert deleted_only.status_code == 200
        assert [entry["id"] for entry in deleted_only.json()["entries"]] == [deleted_internal_fact.entry_id]
    finally:
        app.dependency_overrides.clear()


def test_memory_observability_endpoint_returns_tracker_snapshot():
    class _StubTracker:
        def snapshot(self) -> dict:
            return {
                "window": {"max_samples": 500, "updated_at": "2026-04-13T00:00:00+00:00"},
                "latency": {
                    "retrieval_ms": {"count": 3, "avg": 23.5, "p50": 20.0, "p95": 40.0},
                    "chat_ms": {"count": 3, "avg": 310.0, "p50": 280.0, "p95": 420.0},
                },
                "quality": {
                    "queries": 3,
                    "failures": 0,
                    "hit_queries": 2,
                    "hit_rate": 0.6667,
                    "avg_hits_per_query": 1.0,
                    "avg_similarity": 0.88,
                },
                "write": {"attempts": 3, "failures": 0, "failure_rate": 0.0},
                "alerts": [],
                "thresholds": {
                    "retrieval_p95_ms": 120.0,
                    "chat_p95_ms": 1500.0,
                    "write_failure_rate": 0.01,
                    "retrieval_hit_rate": 0.4,
                },
            }

    original_tracker = getattr(app.state, "knowledge_observability_tracker", None)
    app.state.knowledge_observability_tracker = _StubTracker()

    try:
        client = TestClient(app)
        response = client.get("/memory/observability")
        assert response.status_code == 200
        payload = response.json()
        assert payload["latency"]["retrieval_ms"]["p95"] == 40.0
        assert payload["quality"]["hit_rate"] == 0.6667
        assert payload["write"]["failure_rate"] == 0.0
    finally:
        if original_tracker is None:
            delattr(app.state, "knowledge_observability_tracker")
        else:
            app.state.knowledge_observability_tracker = original_tracker


def test_memory_observability_reset_endpoint_clears_tracker():
    from app.memory.observability import KnowledgeObservabilityTracker

    tracker = KnowledgeObservabilityTracker(max_samples=32)
    tracker.record_retrieval(latency_ms=300.0, hit_count=0, failed=False)
    tracker.record_chat_latency(2500.0)
    tracker.record_write(success=False)

    original_tracker = getattr(app.state, "knowledge_observability_tracker", None)
    app.state.knowledge_observability_tracker = tracker
    try:
        client = TestClient(app)
        reset_response = client.post("/memory/observability/reset")
        assert reset_response.status_code == 200
        assert reset_response.json() == {"success": True, "reset": True}

        snapshot_response = client.get("/memory/observability")
        assert snapshot_response.status_code == 200
        snapshot = snapshot_response.json()
        assert snapshot["latency"]["retrieval_ms"]["count"] == 0
        assert snapshot["latency"]["chat_ms"]["count"] == 0
        assert snapshot["quality"]["queries"] == 0
        assert snapshot["write"]["attempts"] == 0
    finally:
        if original_tracker is None:
            delattr(app.state, "knowledge_observability_tracker")
        else:
            app.state.knowledge_observability_tracker = original_tracker
