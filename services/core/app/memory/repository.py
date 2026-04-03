from pathlib import Path
from typing import Protocol

from app.memory.models import MemoryEvent


class MemoryRepository(Protocol):
    def save_event(self, event: MemoryEvent) -> None:
        ...

    def list_recent(self, limit: int) -> list[MemoryEvent]:
        ...


class InMemoryMemoryRepository:
    def __init__(self) -> None:
        self._events: list[MemoryEvent] = []

    def save_event(self, event: MemoryEvent) -> None:
        self._events.append(event)

    def list_recent(self, limit: int) -> list[MemoryEvent]:
        return list(reversed(self._events[-limit:]))


class FileMemoryRepository:
    def __init__(self, storage_path: Path) -> None:
        self.storage_path = storage_path

    def save_event(self, event: MemoryEvent) -> None:
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        with self.storage_path.open("a", encoding="utf-8") as handle:
            handle.write(event.model_dump_json())
            handle.write("\n")

    def list_recent(self, limit: int) -> list[MemoryEvent]:
        if not self.storage_path.exists():
            return []

        with self.storage_path.open("r", encoding="utf-8") as handle:
            lines = [line.strip() for line in handle.readlines() if line.strip()]

        events = [MemoryEvent.model_validate_json(line) for line in lines[-limit:]]
        return list(reversed(events))
