from __future__ import annotations

from collections import OrderedDict

import pytest
from pydantic import ValidationError

from app.memory.mempalace_repository import MemPalaceMemoryRepository
from app.memory.models import MemoryEvent
from app.memory.repository import InMemoryMemoryRepository


class _FakeCollection:
    def __init__(self) -> None:
        self._rows: OrderedDict[str, tuple[str, dict]] = OrderedDict()

    def upsert(self, *, ids, documents, metadatas):
        for doc_id, doc, meta in zip(ids, documents, metadatas, strict=False):
            self._rows[doc_id] = (doc, dict(meta))

    def get(self, *, ids=None, where=None, include=None, limit=None):
        include = include or []

        selected: list[tuple[str, str, dict]] = []
        if ids is not None:
            for doc_id in ids:
                row = self._rows.get(doc_id)
                if row is None:
                    continue
                selected.append((doc_id, row[0], row[1]))
        else:
            for doc_id, (doc, meta) in self._rows.items():
                if where is not None and not _matches_where(meta, where):
                    continue
                selected.append((doc_id, doc, meta))

        if limit is not None:
            selected = selected[:limit]

        payload = {"ids": [doc_id for doc_id, _, _ in selected]}
        if "documents" in include:
            payload["documents"] = [doc for _, doc, _ in selected]
        if "metadatas" in include:
            payload["metadatas"] = [meta for _, _, meta in selected]
        return payload

    def delete(self, *, ids):
        for doc_id in ids:
            self._rows.pop(doc_id, None)


def _matches_where(meta: dict, where: dict) -> bool:
    clauses = where.get("$and")
    if not isinstance(clauses, list):
        return True

    for clause in clauses:
        if not isinstance(clause, dict):
            return False
        for key, value in clause.items():
            if meta.get(key) != value:
                return False
    return True


def _build_mempalace_repo(collection: _FakeCollection, *, room: str = "chat_exchange_events", chat_room: str | None = None):
    repo = MemPalaceMemoryRepository(
        palace_path="/tmp/palace",
        wing="wing_xiaoyan",
        room=room,
        chat_room=chat_room,
    )
    repo._get_collection = lambda create: collection  # type: ignore[method-assign]
    return repo


def test_repository_saves_event_and_returns_recent_items():
    repo = InMemoryMemoryRepository()
    event = MemoryEvent(kind="episode", content="她在醒来后主动问候用户")
    repo.save_event(event)
    recent = repo.list_recent(limit=5)
    assert recent[0].content == "她在醒来后主动问候用户"
    assert recent[0].entry_id == event.entry_id


def test_memory_event_defaults_long_term_schema_fields():
    event = MemoryEvent(kind="semantic", content="她学会了新的知识点")

    assert event.namespace == "long_term"
    assert event.visibility == "internal"
    assert event.facet is None
    assert event.source_ref is None
    assert event.version_tag is None


def test_memory_event_rejects_invalid_namespace():
    with pytest.raises(ValidationError):
        MemoryEvent(kind="chat", role="user", content="hello", namespace="invalid_namespace")


def test_mempalace_repository_persists_events_across_instances():
    collection = _FakeCollection()

    writer = _build_mempalace_repo(collection)
    writer.save_event(
        MemoryEvent(
            kind="chat",
            role="user",
            content="你好，小燕",
        )
    )

    reader = _build_mempalace_repo(collection)
    recent = reader.list_recent(limit=5)

    assert recent[0].kind == "chat"
    assert recent[0].role == "user"
    assert recent[0].content == "你好，小燕"


def test_in_memory_repository_returns_relevant_events_before_irrelevant_recent_ones():
    repo = InMemoryMemoryRepository()
    repo.save_event(MemoryEvent(kind="chat", role="user", content="我们讨论过星星和夜空"))
    repo.save_event(MemoryEvent(kind="chat", role="assistant", content="后来又聊了早餐"))
    repo.save_event(MemoryEvent(kind="chat", role="user", content="今天想整理文件"))

    relevant = repo.search_relevant("还记得星星吗", limit=2)

    assert [event.content for event in relevant] == [
        "我们讨论过星星和夜空",
        "后来又聊了早餐",
    ]


def test_mempalace_repository_update_and_delete_event():
    collection = _FakeCollection()
    repo = _build_mempalace_repo(collection)

    event = MemoryEvent(kind="chat", role="assistant", content="原始内容")
    repo.save_event(event)

    updated = repo.update_event(event.entry_id, content="更新后内容")
    assert updated is True

    recent = repo.list_recent(limit=10)
    assert [item.content for item in recent] == ["更新后内容"]

    deleted = repo.delete_event(event.entry_id)
    assert deleted is True
    assert repo.list_recent(limit=10) == []


def test_in_memory_repository_soft_delete_filters_active_and_deleted_views():
    repo = InMemoryMemoryRepository()
    active = MemoryEvent(kind="chat", role="user", content="活跃记忆")
    deleted = MemoryEvent(kind="chat", role="assistant", content="将被软删除")
    repo.save_event(active)
    repo.save_event(deleted)

    assert repo.soft_delete_event(deleted.entry_id) is True

    active_recent = repo.list_recent(limit=10, status="active")
    deleted_recent = repo.list_recent(limit=10, status="deleted")
    all_recent = repo.list_recent(limit=10, status="all")

    assert [event.entry_id for event in active_recent] == [active.entry_id]
    assert [event.entry_id for event in deleted_recent] == [deleted.entry_id]
    assert {event.entry_id for event in all_recent} == {active.entry_id, deleted.entry_id}


def test_mempalace_repository_soft_delete_and_restore():
    collection = _FakeCollection()
    repo = _build_mempalace_repo(collection)

    event = MemoryEvent(kind="semantic", content="可恢复记忆")
    repo.save_event(event)

    assert repo.soft_delete_event(event.entry_id) is True
    assert [item.entry_id for item in repo.list_recent(limit=10)] == []
    assert [item.entry_id for item in repo.list_recent(limit=10, status="deleted")] == [event.entry_id]

    assert repo.restore_event(event.entry_id) is True
    assert [item.entry_id for item in repo.list_recent(limit=10)] == [event.entry_id]


def test_mempalace_repository_persists_namespace_and_visibility_metadata():
    collection = _FakeCollection()
    repo = _build_mempalace_repo(collection)

    event = MemoryEvent(
        kind="semantic",
        content="用户偏好把当前牵挂整理成清晰结构",
        facet="preference",
        tags=["preference", "user-profile"],
        source_ref="conversation://2026-04-12/session-1",
        version_tag="v1",
        visibility="user",
    )
    repo.save_event(event)

    payload = collection.get(ids=[f"memory_event:{event.entry_id}"], include=["metadatas"])
    metadata = payload["metadatas"][0]

    assert metadata["namespace"] == "long_term"
    assert metadata["visibility"] == "user"
    assert metadata["facet"] == "preference"
    assert metadata["tags"] == "preference,user-profile"
    assert metadata["source_ref"] == "conversation://2026-04-12/session-1"
    assert metadata["version_tag"] == "v1"


def test_mempalace_repository_clear_all_removes_event_room_and_chat_room_rows():
    collection = _FakeCollection()
    repo = _build_mempalace_repo(collection, room="chat_exchange_events", chat_room="chat_exchange")

    event = MemoryEvent(kind="chat", role="user", content="event-room")
    repo.save_event(event)

    collection.upsert(
        ids=["drawer_chat_room_1"],
        documents=["> hi\nhello"],
        metadatas=[{"wing": "wing_xiaoyan", "room": "chat_exchange"}],
    )

    removed = repo.clear_all()
    assert removed == 2
    assert repo.list_recent(limit=10) == []
    assert collection.get(where={"$and": [{"wing": "wing_xiaoyan"}, {"room": "chat_exchange"}]}, include=[])["ids"] == []
