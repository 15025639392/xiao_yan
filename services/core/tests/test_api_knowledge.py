from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.main import app, get_memory_service
from app.memory.models import MemoryEvent
from app.memory.repository import InMemoryMemoryRepository
from app.memory.service import MemoryService


def test_knowledge_items_endpoint_lists_knowledge_namespace_only():
    repository = InMemoryMemoryRepository()
    memory_service = MemoryService(repository=repository)

    repository.save_event(
        MemoryEvent(
            kind="fact",
            content="用户偏好：晨间同步",
            namespace="knowledge",
            knowledge_type="preference",
        )
    )
    repository.save_event(
        MemoryEvent(
            kind="chat",
            role="user",
            content="这是一条聊天消息",
            namespace="chat",
        )
    )

    def override_memory_service():
        return memory_service

    app.dependency_overrides[get_memory_service] = override_memory_service

    try:
        client = TestClient(app)
        response = client.get("/knowledge/items")
        assert response.status_code == 200
        payload = response.json()
        assert payload["total_count"] == 1
        assert payload["items"][0]["namespace"] == "knowledge"
    finally:
        app.dependency_overrides.clear()


def test_create_knowledge_item_persists_with_manual_governance_metadata():
    repository = InMemoryMemoryRepository()
    memory_service = MemoryService(repository=repository)

    def override_memory_service():
        return memory_service

    app.dependency_overrides[get_memory_service] = override_memory_service

    try:
        client = TestClient(app)
        response = client.post(
            "/knowledge/items",
            json={
                "kind": "fact",
                "content": "用户偏好：输出先给结论再给细节",
                "knowledge_type": "preference",
                "knowledge_tags": ["preference", "user-profile"],
                "source_ref": "manual://operator",
                "reviewer": "ops",
            },
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["item"]["namespace"] == "knowledge"
        assert payload["item"]["governance_source"] == "manual"
        assert payload["item"]["review_status"] == "approved"
        assert payload["item"]["reviewed_by"] == "ops"
    finally:
        app.dependency_overrides.clear()


def test_review_knowledge_item_updates_review_status():
    repository = InMemoryMemoryRepository()
    memory_service = MemoryService(repository=repository)
    seed_event = MemoryEvent(
        kind="fact",
        content="用户边界：讨论前需要先给背景信息",
        namespace="knowledge",
        knowledge_type="boundary",
    )
    repository.save_event(seed_event)

    def override_memory_service():
        return memory_service

    app.dependency_overrides[get_memory_service] = override_memory_service

    try:
        client = TestClient(app)
        response = client.post(
            f"/knowledge/items/{seed_event.entry_id}/review",
            json={
                "decision": "approve",
                "reviewer": "knowledge-owner",
                "review_note": "内容准确，可发布",
            },
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["item"]["review_status"] == "approved"
        assert payload["item"]["reviewed_by"] == "knowledge-owner"
        assert payload["item"]["review_note"] == "内容准确，可发布"
    finally:
        app.dependency_overrides.clear()


def test_review_knowledge_item_reject_requires_review_note():
    repository = InMemoryMemoryRepository()
    memory_service = MemoryService(repository=repository)
    seed_event = MemoryEvent(
        kind="fact",
        content="用户偏好：回复不要太长",
        namespace="knowledge",
    )
    repository.save_event(seed_event)

    def override_memory_service():
        return memory_service

    app.dependency_overrides[get_memory_service] = override_memory_service

    try:
        client = TestClient(app)
        response = client.post(
            f"/knowledge/items/{seed_event.entry_id}/review",
            json={
                "decision": "reject",
                "reviewer": "knowledge-owner",
            },
        )
        assert response.status_code == 400
        assert "review_note" in response.json()["detail"]
    finally:
        app.dependency_overrides.clear()


def test_batch_review_knowledge_items_updates_status_and_returns_summary():
    repository = InMemoryMemoryRepository()
    memory_service = MemoryService(repository=repository)
    event_a = MemoryEvent(kind="fact", content="知识A", namespace="knowledge")
    event_b = MemoryEvent(kind="fact", content="知识B", namespace="knowledge", review_status="pending_review")
    repository.save_event(event_a)
    repository.save_event(event_b)

    def override_memory_service():
        return memory_service

    app.dependency_overrides[get_memory_service] = override_memory_service

    try:
        client = TestClient(app)
        response = client.post(
            "/knowledge/items/review-batch",
            json={
                "knowledge_ids": [event_a.entry_id, event_b.entry_id],
                "decision": "approve",
                "reviewer": "knowledge-owner",
                "review_note": "批量通过",
            },
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["success"] is True
        assert payload["updated"] == 2
        assert payload["failed"] == 0
        assert payload["decision"] == "approve"
        assert set(payload["updated_ids"]) == {event_a.entry_id, event_b.entry_id}

        timeline = client.get("/knowledge/items", params={"review_status": "approved"})
        assert timeline.status_code == 200
        ids = {item["id"] for item in timeline.json()["items"]}
        assert event_a.entry_id in ids
        assert event_b.entry_id in ids
    finally:
        app.dependency_overrides.clear()


def test_batch_review_reject_requires_review_note():
    repository = InMemoryMemoryRepository()
    memory_service = MemoryService(repository=repository)
    event_a = MemoryEvent(kind="fact", content="知识A", namespace="knowledge")
    repository.save_event(event_a)

    def override_memory_service():
        return memory_service

    app.dependency_overrides[get_memory_service] = override_memory_service

    try:
        client = TestClient(app)
        response = client.post(
            "/knowledge/items/review-batch",
            json={
                "knowledge_ids": [event_a.entry_id],
                "decision": "reject",
                "reviewer": "knowledge-owner",
            },
        )
        assert response.status_code == 400
        assert "review_note" in response.json()["detail"]
    finally:
        app.dependency_overrides.clear()


def test_knowledge_items_supports_sort_controls_for_created_at():
    repository = InMemoryMemoryRepository()
    memory_service = MemoryService(repository=repository)
    now = datetime.now(timezone.utc)
    older = MemoryEvent(
        kind="fact",
        content="旧知识",
        namespace="knowledge",
        created_at=now - timedelta(days=2),
    )
    newer = MemoryEvent(
        kind="fact",
        content="新知识",
        namespace="knowledge",
        created_at=now - timedelta(hours=1),
    )
    repository.save_event(older)
    repository.save_event(newer)

    def override_memory_service():
        return memory_service

    app.dependency_overrides[get_memory_service] = override_memory_service

    try:
        client = TestClient(app)
        response_desc = client.get("/knowledge/items", params={"sort_by": "created_at", "sort_order": "desc"})
        assert response_desc.status_code == 200
        items_desc = response_desc.json()["items"]
        assert [item["content"] for item in items_desc] == ["新知识", "旧知识"]

        response_asc = client.get("/knowledge/items", params={"sort_by": "created_at", "sort_order": "asc"})
        assert response_asc.status_code == 200
        items_asc = response_asc.json()["items"]
        assert [item["content"] for item in items_asc] == ["旧知识", "新知识"]
    finally:
        app.dependency_overrides.clear()


def test_knowledge_items_supports_cursor_pagination():
    repository = InMemoryMemoryRepository()
    memory_service = MemoryService(repository=repository)
    now = datetime.now(timezone.utc)
    events = [
        MemoryEvent(kind="fact", content="知识-1", namespace="knowledge", created_at=now - timedelta(minutes=5)),
        MemoryEvent(kind="fact", content="知识-2", namespace="knowledge", created_at=now - timedelta(minutes=4)),
        MemoryEvent(kind="fact", content="知识-3", namespace="knowledge", created_at=now - timedelta(minutes=3)),
        MemoryEvent(kind="fact", content="知识-4", namespace="knowledge", created_at=now - timedelta(minutes=2)),
    ]
    for event in events:
        repository.save_event(event)

    def override_memory_service():
        return memory_service

    app.dependency_overrides[get_memory_service] = override_memory_service

    try:
        client = TestClient(app)
        first_page = client.get(
            "/knowledge/items",
            params={"limit": 2, "sort_by": "created_at", "sort_order": "desc"},
        )
        assert first_page.status_code == 200
        first_payload = first_page.json()
        assert [item["content"] for item in first_payload["items"]] == ["知识-4", "知识-3"]
        assert isinstance(first_payload.get("next_cursor"), str)

        second_page = client.get(
            "/knowledge/items",
            params={
                "limit": 2,
                "sort_by": "created_at",
                "sort_order": "desc",
                "cursor": first_payload["next_cursor"],
            },
        )
        assert second_page.status_code == 200
        second_payload = second_page.json()
        assert [item["content"] for item in second_payload["items"]] == ["知识-2", "知识-1"]
        assert second_payload.get("next_cursor") is None
    finally:
        app.dependency_overrides.clear()


def test_knowledge_items_rejects_using_cursor_and_offset_together():
    repository = InMemoryMemoryRepository()
    memory_service = MemoryService(repository=repository)
    repository.save_event(MemoryEvent(kind="fact", content="知识-1", namespace="knowledge"))
    repository.save_event(MemoryEvent(kind="fact", content="知识-2", namespace="knowledge"))

    def override_memory_service():
        return memory_service

    app.dependency_overrides[get_memory_service] = override_memory_service

    try:
        client = TestClient(app)
        first_page = client.get("/knowledge/items", params={"limit": 1})
        assert first_page.status_code == 200
        cursor = first_page.json().get("next_cursor")
        assert isinstance(cursor, str)

        invalid = client.get("/knowledge/items", params={"limit": 1, "offset": 1, "cursor": cursor})
        assert invalid.status_code == 400
        assert "cursor and offset" in invalid.json()["detail"]
    finally:
        app.dependency_overrides.clear()
