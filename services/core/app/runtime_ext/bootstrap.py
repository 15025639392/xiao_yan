from __future__ import annotations

import asyncio
from logging import getLogger
from pathlib import Path
from threading import Event, Thread

from fastapi import FastAPI

from app.agent.loop import AutonomyLoop
from app.config import (
    get_goal_admission_chain_defer_score,
    get_goal_admission_chain_min_score,
    get_goal_admission_defer_score,
    get_goal_admission_max_retries,
    get_goal_admission_min_score,
    get_goal_admission_mode,
    get_goal_admission_storage_path,
    get_goal_wip_limit,
    get_goal_storage_path,
    get_mempalace_palace_path,
    get_mempalace_results_limit,
    get_mempalace_room,
    get_mempalace_wing,
    get_persona_storage_path,
    get_state_storage_path,
    get_world_storage_path,
)
from app.goals.admission import GoalAdmissionService, GoalAdmissionStore
from app.goals.repository import FileGoalRepository
from app.memory.mempalace_repository import MemPalaceMemoryRepository
from app.memory.observability import KnowledgeObservabilityTracker
from app.memory.service import MemoryService
from app.memory.mempalace_adapter import MemPalaceAdapter
from app.persona.service import FilePersonaRepository, PersonaService
from app.realtime import AppRealtimeHub
from app.runtime import StateStore
from app.runtime_ext.mac_console_bootstrap import maybe_bootstrap_mac_console_environment
from app.runtime_ext.snapshot import (
    build_app_snapshot,
    build_world_state,
)
from app.world.repository import FileWorldRepository
from app.world.service import WorldStateService

logger = getLogger(__name__)


def ensure_runtime_initialized(target_app: FastAPI) -> None:
    if hasattr(target_app.state, "state_store"):
        return

    target_app.state.mac_console_bootstrap_status = maybe_bootstrap_mac_console_environment()

    palace_path = get_mempalace_palace_path()
    Path(palace_path).mkdir(parents=True, exist_ok=True)

    mempalace_adapter = MemPalaceAdapter(
        enabled=True,
        palace_path=palace_path,
        results_limit=get_mempalace_results_limit(),
        wing=get_mempalace_wing(),
        room=get_mempalace_room(),
    )
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
    goal_repository = FileGoalRepository(get_goal_storage_path())
    goal_admission_service = GoalAdmissionService(
        store=GoalAdmissionStore(get_goal_admission_storage_path()),
        mode=get_goal_admission_mode(),
        min_score=get_goal_admission_min_score(),
        defer_score=get_goal_admission_defer_score(),
        chain_min_score=get_goal_admission_chain_min_score(),
        chain_defer_score=get_goal_admission_chain_defer_score(),
        wip_limit=get_goal_wip_limit(),
        max_retries=get_goal_admission_max_retries(),
    )
    world_repository = FileWorldRepository(get_world_storage_path())
    persona_repository = FilePersonaRepository(get_persona_storage_path())
    persona_service = PersonaService(repository=persona_repository)
    memory_service = MemoryService(
        repository=memory_repository,
        personality=persona_service.profile.personality,
    )
    knowledge_observability_tracker = KnowledgeObservabilityTracker()
    stop_event = Event()

    try:
        from app.llm.gateway import ChatGateway

        loop_gateway = ChatGateway.from_env()
    except Exception:
        loop_gateway = None

    loop = AutonomyLoop(
        state_store,
        memory_repository,
        goal_repository,
        goal_admission_service=goal_admission_service,
        gateway=loop_gateway,
    )
    world_state_service = WorldStateService()

    build_world_state(
        state_store,
        goal_repository,
        memory_repository,
        world_repository,
        world_state_service,
    )

    def run_loop() -> None:
        while not stop_event.wait(5.0):
            loop.tick_once()

    worker = Thread(target=run_loop, name="autonomy-loop", daemon=True)
    worker.start()

    target_app.state.state_store = state_store
    target_app.state.memory_repository = memory_repository
    target_app.state.goal_repository = goal_repository
    target_app.state.goal_admission_service = goal_admission_service
    target_app.state.world_repository = world_repository
    target_app.state.persona_service = persona_service
    target_app.state.memory_service = memory_service
    target_app.state.knowledge_observability_tracker = knowledge_observability_tracker
    target_app.state.mempalace_adapter = mempalace_adapter
    target_app.state.stop_event = stop_event
    target_app.state.autonomy_thread = worker
    target_app.state.autonomy_loop = loop


def shutdown_runtime(target_app: FastAPI) -> None:
    stop_event = getattr(target_app.state, "stop_event", None)
    worker = getattr(target_app.state, "autonomy_thread", None)
    if stop_event is None or worker is None:
        return
    if worker.is_alive():
        stop_event.set()
        worker.join(timeout=1.0)


def reload_runtime(target_app: FastAPI) -> None:
    shutdown_runtime(target_app)
    runtime_state_attrs = [
        "state_store",
        "memory_repository",
        "goal_repository",
        "goal_admission_service",
        "world_repository",
        "persona_service",
        "memory_service",
        "knowledge_observability_tracker",
        "mempalace_adapter",
        "stop_event",
        "autonomy_thread",
        "autonomy_loop",
        "realtime_hub",
    ]
    for attr in runtime_state_attrs:
        if hasattr(target_app.state, attr):
            delattr(target_app.state, attr)
    ensure_runtime_initialized(target_app)


def ensure_realtime_hub_initialized(target_app: FastAPI) -> None:
    existing_hub = getattr(target_app.state, "realtime_hub", None)
    if existing_hub is not None and not existing_hub.loop.is_closed():
        return

    loop = asyncio.get_running_loop()
    hub = AppRealtimeHub(loop=loop, snapshot_builder=lambda: build_app_snapshot(target_app))
    target_app.state.realtime_hub = hub

    state_store = target_app.state.state_store
    memory_repository = target_app.state.memory_repository
    goal_repository = target_app.state.goal_repository
    persona_service = target_app.state.persona_service
    goal_admission_service = target_app.state.goal_admission_service

    if hasattr(state_store, "set_on_change_callback"):
        state_store.set_on_change_callback(hub.publish_runtime)
    if hasattr(memory_repository, "set_on_change_callback"):
        memory_repository.set_on_change_callback(lambda: (hub.publish_runtime(), hub.publish_memory()))
    if hasattr(goal_repository, "set_on_change_callback"):
        goal_repository.set_on_change_callback(hub.publish_runtime)
    if hasattr(goal_admission_service, "set_on_change_callback"):
        goal_admission_service.set_on_change_callback(hub.publish_runtime)
    if hasattr(persona_service, "set_on_change_callback"):
        persona_service.set_on_change_callback(hub.publish_persona)

    try:
        hub.warm_snapshot_cache()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Realtime snapshot warmup failed: %s", exc)
