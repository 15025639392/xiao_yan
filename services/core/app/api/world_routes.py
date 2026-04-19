from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import (
    get_memory_repository,
    get_state_store,
    get_world_repository,
    get_world_state_service,
)
from app.domain.models import FocusMode, WakeMode
from app.memory.repository import MemoryRepository
from app.runtime import StateStore
from app.runtime_ext.bootstrap import build_world_state
from app.runtime_ext.snapshot import build_public_state_payload, find_recent_autobio
from app.usecases.lifecycle import wake_up
from app.world.repository import WorldRepository
from app.world.service import WorldStateService


def build_world_router() -> APIRouter:
    router = APIRouter()

    @router.get("/world")
    def get_world(
        state_store: StateStore = Depends(get_state_store),
        memory_repository: MemoryRepository = Depends(get_memory_repository),
        world_repository: WorldRepository = Depends(get_world_repository),
        world_state_service: WorldStateService = Depends(get_world_state_service),
    ) -> dict:
        world_state = build_world_state(
            state_store,
            memory_repository,
            world_repository,
            world_state_service,
        )
        return world_state.model_dump()

    @router.post("/lifecycle/wake")
    def wake(
        state_store: StateStore = Depends(get_state_store),
        memory_repository: MemoryRepository = Depends(get_memory_repository),
    ) -> dict:
        current_state = state_store.get()
        recent_autobio = find_recent_autobio(memory_repository)
        waking_state = wake_up(recent_autobio=recent_autobio).model_copy(
            update={
                "last_proactive_source": current_state.last_proactive_source,
                "last_proactive_at": current_state.last_proactive_at,
            }
        )
        return build_public_state_payload(state_store.set(waking_state))

    @router.post("/lifecycle/sleep")
    def sleep(
        state_store: StateStore = Depends(get_state_store),
    ) -> dict:
        current_state = state_store.get()
        sleeping_state = current_state.model_copy(
            update={
                "mode": WakeMode.SLEEPING,
                "focus_mode": FocusMode.SLEEPING,
                "current_thought": None,
                "focus_subject": None,
                "focus_effort": None,
                "last_action": None,
            }
        )
        return build_public_state_payload(state_store.set(sleeping_state))

    return router
