from __future__ import annotations

import asyncio
from datetime import datetime
from logging import getLogger
from threading import Event, Thread
from typing import Any

from fastapi import FastAPI

from app.agent.loop import AutonomyLoop
from app.config import (
    get_goal_storage_path,
    get_memory_storage_path,
    get_persona_storage_path,
    get_state_storage_path,
    get_world_storage_path,
)
from app.goals.repository import FileGoalRepository, GoalRepository
from app.llm.schemas import ChatHistoryMessage, ChatMessage
from app.memory.repository import FileMemoryRepository, MemoryRepository
from app.memory.service import MemoryService
from app.persona.service import FilePersonaRepository, PersonaService
from app.realtime import AppRealtimeHub
from app.runtime import StateStore
from app.world.models import WorldState
from app.world.repository import FileWorldRepository, WorldRepository
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
    world_repository = FileWorldRepository(get_world_storage_path())
    persona_repository = FilePersonaRepository(get_persona_storage_path())
    persona_service = PersonaService(repository=persona_repository)
    memory_service = MemoryService(
        repository=memory_repository,
        personality=persona_service.profile.personality,
    )
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
    target_app.state.world_repository = world_repository
    target_app.state.persona_service = persona_service
    target_app.state.memory_service = memory_service
    target_app.state.stop_event = stop_event
    target_app.state.autonomy_thread = worker


def shutdown_runtime(target_app: FastAPI) -> None:
    stop_event = getattr(target_app.state, "stop_event", None)
    worker = getattr(target_app.state, "autonomy_thread", None)
    if stop_event is None or worker is None:
        return
    if worker.is_alive():
        stop_event.set()
        worker.join(timeout=1.0)


def _compose_world_state(
    state_store: StateStore,
    goal_repository: GoalRepository,
    memory_repository: MemoryRepository,
    world_state_service: WorldStateService,
) -> WorldState:
    state = state_store.get()
    focused_goals = [
        goal
        for goal_id in state.active_goal_ids
        if (goal := goal_repository.get_goal(goal_id)) is not None
    ]
    latest_world_event = next((event for event in memory_repository.list_recent(limit=20) if event.kind == "world"), None)
    return world_state_service.bootstrap(
        being_state=state,
        focused_goals=focused_goals,
        latest_event=None if latest_world_event is None else latest_world_event.content,
        latest_event_at=None if latest_world_event is None else latest_world_event.created_at,
    )


def build_world_state(
    state_store: StateStore,
    goal_repository: GoalRepository,
    memory_repository: MemoryRepository,
    world_repository: WorldRepository,
    world_state_service: WorldStateService,
) -> WorldState:
    world_state = _compose_world_state(state_store, goal_repository, memory_repository, world_state_service)
    return world_repository.save_world_state(world_state)


def build_chat_messages(
    memory_repository: MemoryRepository,
    state_store: StateStore,
    goal_repository: GoalRepository,
    user_message: str,
    *,
    limit: int,
) -> list[ChatMessage]:
    relevant_events = memory_repository.search_relevant(user_message, limit=limit)
    state = state_store.get()
    focus_goal = None if not state.active_goal_ids else goal_repository.get_goal(state.active_goal_ids[0])
    focus_messages = (
        []
        if focus_goal is None
        else [ChatMessage(role="system", content=f"你当前最在意的焦点目标：{focus_goal.title}。")]
    )
    latest_plan_completion = find_latest_today_plan_completion(memory_repository)
    completion_messages = (
        []
        if latest_plan_completion is None
        else [ChatMessage(role="system", content=f"你今天刚完成的一件事：{latest_plan_completion}")]
    )
    world_messages = [
        ChatMessage(role="system", content=f"最近你的世界事件：{event.content}")
        for event in relevant_events
        if event.kind == "world"
    ]
    inner_messages = [
        ChatMessage(role="system", content=f"最近你的内在阶段记忆：{event.content}")
        for event in relevant_events
        if event.kind == "inner"
    ]
    autobio_messages = [
        ChatMessage(role="system", content=f"最近你的自传式回顾：{event.content}")
        for event in relevant_events
        if event.kind == "autobio"
    ]
    messages = [
        ChatMessage(role=event.role, content=event.content)
        for event in relevant_events
        if event.kind == "chat" and event.role in {"user", "assistant"}
    ]
    messages.append(ChatMessage(role="user", content=user_message))
    return [*focus_messages, *completion_messages, *world_messages, *inner_messages, *autobio_messages, *messages]


def deduplicate_entries(entries: list[str]) -> list[str]:
    unique_entries: list[str] = []
    seen: set[str] = set()
    for entry in entries:
        if entry in seen:
            continue
        seen.add(entry)
        unique_entries.append(entry)
    return unique_entries


def find_recent_autobio(memory_repository: MemoryRepository) -> str | None:
    recent_events = memory_repository.list_recent(limit=20)
    return next((event.content for event in recent_events if event.kind == "autobio"), None)


def find_latest_today_plan_completion(memory_repository: MemoryRepository) -> str | None:
    recent_events = memory_repository.list_recent(limit=20)
    return next(
        (event.content for event in recent_events if event.kind == "autobio" and "今天的计划" in event.content),
        None,
    )


def build_runtime_payload(target_app: FastAPI) -> dict[str, Any]:
    state_store: StateStore = target_app.state.state_store
    memory_repository: MemoryRepository = target_app.state.memory_repository
    goal_repository: GoalRepository = target_app.state.goal_repository

    messages = [
        ChatHistoryMessage(
            id=event.entry_id,
            role=event.role,
            content=event.content,
            created_at=event.created_at.isoformat() if event.created_at else None,
            session_id=event.session_id,
        ).model_dump()
        for event in reversed(memory_repository.list_recent(limit=20))
        if event.kind == "chat" and event.role in {"user", "assistant"}
    ]
    autobio_entries = [event.content for event in reversed(memory_repository.list_recent(limit=20)) if event.kind == "autobio"]
    world_state = _compose_world_state(
        state_store,
        goal_repository,
        memory_repository,
        WorldStateService(),
    )
    return {
        "state": state_store.get().model_dump(mode="json"),
        "messages": messages,
        "goals": [goal.model_dump(mode="json") for goal in goal_repository.list_goals()],
        "world": world_state.model_dump(mode="json"),
        "autobio": deduplicate_entries(autobio_entries),
    }


def build_memory_payload(target_app: FastAPI) -> dict[str, Any]:
    memory_service: MemoryService = target_app.state.memory_service
    return {"summary": memory_service.get_memory_summary(), "timeline": memory_service.get_memory_timeline(limit=40)}


def build_persona_payload(target_app: FastAPI) -> dict[str, Any]:
    persona_service: PersonaService = target_app.state.persona_service
    return {"profile": persona_service.get_profile().model_dump(mode="json"), "emotion": persona_service.get_emotion_summary()}


def build_app_snapshot(target_app: FastAPI) -> dict[str, Any]:
    return {"runtime": build_runtime_payload(target_app), "memory": build_memory_payload(target_app), "persona": build_persona_payload(target_app)}


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

