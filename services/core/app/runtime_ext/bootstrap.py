from __future__ import annotations

import asyncio
from logging import getLogger
from threading import Event, Thread

from fastapi import FastAPI

from app.agent.loop import AutonomyLoop
from app.config import (
    get_goal_storage_path,
    get_goal_admission_defer_score,
    get_goal_admission_max_retries,
    get_goal_admission_min_score,
    get_goal_admission_mode,
    get_goal_admission_storage_path,
    get_goal_wip_limit,
    is_goal_admission_world_enabled,
    get_memory_storage_path,
    get_persona_storage_path,
    get_state_storage_path,
    get_world_storage_path,
)
from app.goals.admission import GoalAdmissionService, GoalAdmissionStore
from app.goals.repository import FileGoalRepository
from app.memory.repository import FileMemoryRepository
from app.memory.service import MemoryService
from app.persona.service import FilePersonaRepository, PersonaService
from app.realtime import AppRealtimeHub
from app.runtime import StateStore
from app.runtime_ext.snapshot import (
    build_app_snapshot,
    build_chat_messages,
    build_memory_payload,
    build_persona_payload,
    build_runtime_payload,
    build_world_state,
    deduplicate_entries,
    find_latest_today_plan_completion,
    find_recent_autobio,
)
from app.self_programming.history_store import SelfProgrammingHistory
from app.world.repository import FileWorldRepository
from app.world.service import WorldStateService

logger = getLogger(__name__)


def ensure_runtime_initialized(target_app: FastAPI) -> None:
    if hasattr(target_app.state, "state_store"):
        return

    memory_repository = FileMemoryRepository(get_memory_storage_path())
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
        wip_limit=get_goal_wip_limit(),
        world_enabled=is_goal_admission_world_enabled(),
        max_retries=get_goal_admission_max_retries(),
    )
    world_repository = FileWorldRepository(get_world_storage_path())
    persona_repository = FilePersonaRepository(get_persona_storage_path())
    persona_service = PersonaService(repository=persona_repository)
    memory_service = MemoryService(
        repository=memory_repository,
        personality=persona_service.profile.personality,
    )
    stop_event = Event()
    self_programming_history = SelfProgrammingHistory(
        storage_path=get_state_storage_path().parent / ".self-programming-history.json",
    )

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
        self_programming_history=self_programming_history,
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
    target_app.state.stop_event = stop_event
    target_app.state.autonomy_thread = worker
    target_app.state.autonomy_loop = loop
    target_app.state.self_programming_history = self_programming_history


def shutdown_runtime(target_app: FastAPI) -> None:
    stop_event = getattr(target_app.state, "stop_event", None)
    worker = getattr(target_app.state, "autonomy_thread", None)
    if stop_event is None or worker is None:
        return
    if worker.is_alive():
        stop_event.set()
        worker.join(timeout=1.0)


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

    if hasattr(state_store, "set_on_change_callback"):
        state_store.set_on_change_callback(hub.publish_runtime)
    if hasattr(memory_repository, "set_on_change_callback"):
        memory_repository.set_on_change_callback(lambda: (hub.publish_runtime(), hub.publish_memory()))
    if hasattr(goal_repository, "set_on_change_callback"):
        goal_repository.set_on_change_callback(hub.publish_runtime)
    if hasattr(persona_service, "set_on_change_callback"):
        persona_service.set_on_change_callback(hub.publish_persona)
