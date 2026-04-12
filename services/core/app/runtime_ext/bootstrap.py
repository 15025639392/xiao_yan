from __future__ import annotations

import asyncio
from datetime import timedelta
from logging import getLogger
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
    get_goal_admission_world_defer_score,
    get_goal_admission_world_min_score,
    get_goal_wip_limit,
    get_goal_storage_path,
    get_orchestrator_delegate_followup_interval_minutes,
    get_orchestrator_delegate_no_receipt_hours,
    get_orchestrator_delegate_soft_ping_hours,
    get_orchestrator_max_parallel_sessions,
    get_orchestrator_max_parallel_tasks_per_session,
    get_orchestrator_message_storage_path,
    get_orchestrator_storage_path,
    get_mempalace_palace_path,
    get_mempalace_results_limit,
    get_mempalace_room,
    get_mempalace_wing,
    get_persona_storage_path,
    get_state_storage_path,
    get_world_storage_path,
    is_goal_admission_world_enabled,
)
from app.goals.admission import GoalAdmissionService, GoalAdmissionStore
from app.goals.repository import FileGoalRepository
from app.memory.mempalace_repository import MemPalaceMemoryRepository
from app.memory.observability import KnowledgeObservabilityTracker
from app.memory.service import MemoryService
from app.memory.mempalace_adapter import MemPalaceAdapter
from app.orchestrator.conversation_repository import OrchestratorConversationRepository
from app.orchestrator.conversation_service import OrchestratorConversationService
from app.orchestrator.repository import OrchestratorSessionRepository
from app.orchestrator.service import OrchestratorService
from app.persona.service import FilePersonaRepository, PersonaService
from app.realtime import AppRealtimeHub
from app.runtime import StateStore
from app.runtime_ext.mac_console_bootstrap import maybe_bootstrap_mac_console_environment
from app.runtime_ext.snapshot import (
    build_app_snapshot,
    build_world_state,
)
from app.self_programming.history_store import SelfProgrammingHistory
from app.world.repository import FileWorldRepository
from app.world.service import WorldStateService

logger = getLogger(__name__)


def ensure_runtime_initialized(target_app: FastAPI) -> None:
    if hasattr(target_app.state, "state_store"):
        return

    target_app.state.mac_console_bootstrap_status = maybe_bootstrap_mac_console_environment()

    mempalace_adapter = MemPalaceAdapter(
        enabled=True,
        palace_path=get_mempalace_palace_path(),
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
        world_min_score=get_goal_admission_world_min_score(),
        world_defer_score=get_goal_admission_world_defer_score(),
        chain_min_score=get_goal_admission_chain_min_score(),
        chain_defer_score=get_goal_admission_chain_defer_score(),
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
    knowledge_observability_tracker = KnowledgeObservabilityTracker()
    stop_event = Event()
    self_programming_history = SelfProgrammingHistory(
        storage_path=get_state_storage_path().parent / ".self-programming-history.json",
    )
    orchestrator_repository = OrchestratorSessionRepository(get_orchestrator_storage_path())
    orchestrator_conversation_repository = OrchestratorConversationRepository(get_orchestrator_message_storage_path())
    orchestrator_conversation_service = OrchestratorConversationService(
        repository=orchestrator_conversation_repository,
        scheduler_provider=lambda: orchestrator_service.get_scheduler_snapshot(),
    )
    orchestrator_service = OrchestratorService(
        repository=orchestrator_repository,
        state_store=state_store,
        conversation_service=orchestrator_conversation_service,
        max_parallel_sessions=get_orchestrator_max_parallel_sessions(),
        max_parallel_tasks_per_session=get_orchestrator_max_parallel_tasks_per_session(),
        delegate_soft_ping_timeout=timedelta(hours=get_orchestrator_delegate_soft_ping_hours()),
        delegate_no_receipt_timeout=timedelta(hours=get_orchestrator_delegate_no_receipt_hours()),
        delegate_stall_followup_interval=timedelta(minutes=get_orchestrator_delegate_followup_interval_minutes()),
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
    target_app.state.knowledge_observability_tracker = knowledge_observability_tracker
    target_app.state.mempalace_adapter = mempalace_adapter
    target_app.state.stop_event = stop_event
    target_app.state.autonomy_thread = worker
    target_app.state.autonomy_loop = loop
    target_app.state.self_programming_history = self_programming_history
    target_app.state.orchestrator_repository = orchestrator_repository
    target_app.state.orchestrator_conversation_repository = orchestrator_conversation_repository
    target_app.state.orchestrator_conversation_service = orchestrator_conversation_service
    target_app.state.orchestrator_service = orchestrator_service

    current_orchestrator_session = state_store.get().orchestrator_session
    if current_orchestrator_session is not None:
        orchestrator_repository.save(current_orchestrator_session)


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
        "self_programming_history",
        "orchestrator_repository",
        "orchestrator_conversation_repository",
        "orchestrator_conversation_service",
        "orchestrator_service",
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
