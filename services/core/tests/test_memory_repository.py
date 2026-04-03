from app.memory.models import MemoryEvent
from app.memory.repository import InMemoryMemoryRepository


def test_repository_saves_event_and_returns_recent_items():
    repo = InMemoryMemoryRepository()
    event = MemoryEvent(kind="episode", content="她在醒来后主动问候用户")
    repo.save_event(event)
    recent = repo.list_recent(limit=5)
    assert recent[0].content == "她在醒来后主动问候用户"
