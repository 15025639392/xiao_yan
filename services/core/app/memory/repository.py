from app.memory.models import MemoryEvent


class InMemoryMemoryRepository:
    def __init__(self) -> None:
        self._events: list[MemoryEvent] = []

    def save_event(self, event: MemoryEvent) -> None:
        self._events.append(event)

    def list_recent(self, limit: int) -> list[MemoryEvent]:
        return list(reversed(self._events[-limit:]))
