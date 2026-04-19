from __future__ import annotations

from pathlib import Path

from app.config import (
    get_mempalace_palace_path,
    get_mempalace_results_limit,
    get_mempalace_room,
    get_mempalace_wing,
    get_persona_storage_path,
    get_state_storage_path,
    get_world_storage_path,
)
from app.memory.chat_memory_runtime import ChatMemoryRuntime
from app.memory.mempalace_adapter import MemPalaceAdapter
from app.memory.mempalace_repository import MemPalaceMemoryRepository
from app.memory.observability import MemoryObservabilityTracker
from app.memory.service import MemoryService
from app.persona.service import FilePersonaRepository, PersonaService
from app.runtime import StateStore
from app.world.repository import FileWorldRepository


def build_mempalace_adapter() -> MemPalaceAdapter:
    palace_path = get_mempalace_palace_path()
    Path(palace_path).mkdir(parents=True, exist_ok=True)
    return MemPalaceAdapter(
        palace_path=palace_path,
        results_limit=get_mempalace_results_limit(),
        wing=get_mempalace_wing(),
        room=get_mempalace_room(),
    )


def build_runtime_services() -> dict[str, object]:
    mempalace_adapter = build_mempalace_adapter()
    memory_repository = MemPalaceMemoryRepository(
        palace_path=mempalace_adapter.palace_path,
        wing=mempalace_adapter.wing,
        room=f"{mempalace_adapter.room}_events",
        chat_room=mempalace_adapter.room,
    )
    state_store = StateStore(
        memory_repository=memory_repository,
        storage_path=get_state_storage_path(),
    )
    world_repository = FileWorldRepository(get_world_storage_path())
    persona_repository = FilePersonaRepository(get_persona_storage_path())
    persona_service = PersonaService(repository=persona_repository)
    memory_service = MemoryService(
        repository=memory_repository,
        personality=persona_service.profile.personality,
    )
    chat_memory_runtime = ChatMemoryRuntime(
        backend=mempalace_adapter,
        repository=memory_repository,
    )

    return {
        "mempalace_adapter": mempalace_adapter,
        "memory_repository": memory_repository,
        "state_store": state_store,
        "world_repository": world_repository,
        "persona_service": persona_service,
        "memory_service": memory_service,
        "chat_memory_runtime": chat_memory_runtime,
        "memory_observability_tracker": MemoryObservabilityTracker(),
    }
