import json
from pathlib import Path
from typing import Protocol

from app.world.models import WorldState


class WorldRepository(Protocol):
    def save_world_state(self, world_state: WorldState) -> WorldState:
        ...

    def get_world_state(self) -> WorldState | None:
        ...


class InMemoryWorldRepository:
    def __init__(self) -> None:
        self._world_state: WorldState | None = None

    def save_world_state(self, world_state: WorldState) -> WorldState:
        self._world_state = world_state
        return world_state

    def get_world_state(self) -> WorldState | None:
        return self._world_state


class FileWorldRepository:
    def __init__(self, storage_path: Path) -> None:
        self.storage_path = storage_path

    def save_world_state(self, world_state: WorldState) -> WorldState:
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self.storage_path.write_text(
            json.dumps(world_state.model_dump(mode="json"), ensure_ascii=False),
            encoding="utf-8",
        )
        return world_state

    def get_world_state(self) -> WorldState | None:
        if not self.storage_path.exists():
            return None

        data = json.loads(self.storage_path.read_text(encoding="utf-8"))
        return WorldState.model_validate(data)
