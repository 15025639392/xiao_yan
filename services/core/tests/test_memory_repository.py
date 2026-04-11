from __future__ import annotations

from collections import OrderedDict

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
