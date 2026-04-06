from pathlib import Path
from typing import Protocol

from app.utils.file_utils import read_json_file, write_json_file
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
        write_json_file(
            self.storage_path,
            world_state.model_dump(mode="json"),
            ensure_ascii=False,
            create_parent=True,
        )
        return world_state

    def get_world_state(self) -> WorldState | None:
        if not self.storage_path.exists():
            return None

        data = read_json_file(self.storage_path)
        return WorldState.model_validate(data)
