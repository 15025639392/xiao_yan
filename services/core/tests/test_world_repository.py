from pathlib import Path

from app.world.models import WorldState
from app.world.repository import FileWorldRepository, InMemoryWorldRepository


def test_in_memory_world_repository_returns_latest_snapshot():
    repository = InMemoryWorldRepository()
    saved = repository.save_world_state(
        WorldState(
            time_of_day="afternoon",
            energy="high",
            mood="engaged",
            focus_tension="high",
        )
    )

    loaded = repository.get_world_state()

    assert loaded == saved
    assert loaded is not None
    assert loaded.energy == "high"


def test_file_world_repository_persists_snapshot_across_instances(tmp_path: Path):
    storage_path = tmp_path / "world.json"
    repository = FileWorldRepository(storage_path)
    repository.save_world_state(
        WorldState(
            time_of_day="night",
            energy="low",
            mood="tired",
            focus_tension="low",
        )
    )

    reloaded = FileWorldRepository(storage_path)
    loaded = reloaded.get_world_state()

    assert loaded is not None
    assert loaded.time_of_day == "night"
    assert loaded.mood == "tired"
