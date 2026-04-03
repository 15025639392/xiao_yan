from pathlib import Path

from app.memory.models import MemoryEvent
from app.memory.repository import FileMemoryRepository, InMemoryMemoryRepository


def test_repository_saves_event_and_returns_recent_items():
    repo = InMemoryMemoryRepository()
    event = MemoryEvent(kind="episode", content="她在醒来后主动问候用户")
    repo.save_event(event)
    recent = repo.list_recent(limit=5)
    assert recent[0].content == "她在醒来后主动问候用户"


def test_file_repository_persists_events_across_instances(tmp_path: Path):
    storage_path = tmp_path / "memory.jsonl"

    writer = FileMemoryRepository(storage_path)
    writer.save_event(
        MemoryEvent(
            kind="chat",
            role="user",
            content="你好，小燕",
        )
    )

    reader = FileMemoryRepository(storage_path)
    recent = reader.list_recent(limit=5)

    assert recent[0].kind == "chat"
    assert recent[0].role == "user"
    assert recent[0].content == "你好，小燕"
