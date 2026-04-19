from __future__ import annotations

import asyncio
from logging import getLogger
from threading import Event, Thread

from fastapi import FastAPI

from app.agent.loop import AutonomyLoop
from app.realtime import AppRealtimeHub
from app.runtime_ext.mac_console_bootstrap import maybe_bootstrap_mac_console_environment
from app.runtime_ext.runtime_services import build_runtime_services
from app.runtime_ext.snapshot import (
    build_app_snapshot,
    build_world_state,
)
from app.world.service import WorldStateService

logger = getLogger(__name__)


def ensure_runtime_initialized(target_app: FastAPI) -> None:
    if hasattr(target_app.state, "state_store"):
        return

    target_app.state.mac_console_bootstrap_status = maybe_bootstrap_mac_console_environment()
    runtime_services = build_runtime_services()
    mempalace_adapter = runtime_services["mempalace_adapter"]
    memory_repository = runtime_services["memory_repository"]
    state_store = runtime_services["state_store"]
    world_repository = runtime_services["world_repository"]
    persona_service = runtime_services["persona_service"]
    memory_service = runtime_services["memory_service"]
    chat_memory_runtime = runtime_services["chat_memory_runtime"]
    memory_observability_tracker = runtime_services["memory_observability_tracker"]
    stop_event = Event()

    try:
        from app.llm.gateway import ChatGateway

        loop_gateway = ChatGateway.from_env()
    except Exception:
        loop_gateway = None

    loop = AutonomyLoop(
        state_store,
        memory_repository,
        gateway=loop_gateway,
    )
    world_state_service = WorldStateService()

    build_world_state(
        state_store,
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
    target_app.state.world_repository = world_repository
    target_app.state.persona_service = persona_service
    target_app.state.memory_service = memory_service
    target_app.state.chat_memory_runtime = chat_memory_runtime
    target_app.state.memory_observability_tracker = memory_observability_tracker
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
        "world_repository",
        "persona_service",
        "memory_service",
        "chat_memory_runtime",
        "memory_observability_tracker",
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
    persona_service = target_app.state.persona_service

    if hasattr(state_store, "set_on_change_callback"):
        state_store.set_on_change_callback(hub.publish_runtime)
    if hasattr(memory_repository, "set_on_change_callback"):
        memory_repository.set_on_change_callback(lambda: (hub.publish_runtime(), hub.publish_memory()))
    if hasattr(persona_service, "set_on_change_callback"):
        persona_service.set_on_change_callback(hub.publish_persona)

    try:
        hub.warm_snapshot_cache()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Realtime snapshot warmup failed: %s", exc)
