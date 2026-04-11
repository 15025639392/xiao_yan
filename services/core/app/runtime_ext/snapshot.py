from __future__ import annotations

from typing import Any

from fastapi import FastAPI

from app.goals.admission import GoalAdmissionService
from app.goals.repository import GoalRepository
from app.llm.schemas import ChatHistoryMessage
from app.memory.repository import MemoryRepository
from app.runtime import StateStore
from app.runtime_ext.runtime_config import get_runtime_config
from app.world.models import WorldState
from app.world.repository import WorldRepository
from app.world.service import WorldStateService

RUNTIME_CHAT_MESSAGES_LIMIT = 80


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
    latest_world_event = next(
        (event for event in memory_repository.list_recent(limit=20) if event.kind == "world"),
        None,
    )
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
    world_state = _compose_world_state(
        state_store,
        goal_repository,
        memory_repository,
        world_state_service,
    )
    return world_repository.save_world_state(world_state)


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


def build_runtime_payload(target_app: FastAPI) -> dict[str, Any]:
    state_store: StateStore = target_app.state.state_store
    memory_repository: MemoryRepository = target_app.state.memory_repository
    goal_repository: GoalRepository = target_app.state.goal_repository
    goal_admission_service: GoalAdmissionService | None = getattr(target_app.state, "goal_admission_service", None)
    mempalace_adapter = getattr(target_app.state, "mempalace_adapter", None)
    messages: list[dict[str, Any]]
    if mempalace_adapter is not None and hasattr(mempalace_adapter, "list_recent_chat_messages"):
        try:
            recent_chat_messages = mempalace_adapter.list_recent_chat_messages(
                limit=RUNTIME_CHAT_MESSAGES_LIMIT,
                offset=0,
            )
        except Exception:  # noqa: BLE001
            recent_chat_messages = []
        messages = [
            ChatHistoryMessage(
                id=str(event.get("id") or ""),
                role=str(event.get("role") or "assistant"),
                content=str(event.get("content") or ""),
                created_at=event.get("created_at"),
                session_id=event.get("session_id"),
            ).model_dump()
            for event in reversed(recent_chat_messages)
            if isinstance(event, dict)
        ]
    else:
        messages = [
            ChatHistoryMessage(
                id=event.entry_id,
                role=event.role,
                content=event.content,
                created_at=event.created_at.isoformat() if event.created_at else None,
                session_id=event.session_id,
            ).model_dump()
            for event in reversed(memory_repository.list_recent_chat(limit=RUNTIME_CHAT_MESSAGES_LIMIT))
        ]
    autobio_entries = [
        event.content
        for event in reversed(memory_repository.list_recent(limit=20))
        if event.kind == "autobio"
    ]
    world_state = _compose_world_state(
        state_store,
        goal_repository,
        memory_repository,
        WorldStateService(),
    )
    runtime_config = get_runtime_config()
    mac_console_status = getattr(target_app.state, "mac_console_bootstrap_status", None)
    return {
        "state": state_store.get().model_dump(mode="json"),
        "messages": messages,
        "goals": [goal.model_dump(mode="json") for goal in goal_repository.list_goals()],
        "goal_admission_stats": (
            None
            if goal_admission_service is None
            else goal_admission_service.get_stats(
                stability_warning_rate=runtime_config.goal_admission_stability_warning_rate,
                stability_danger_rate=runtime_config.goal_admission_stability_danger_rate,
            )
        ),
        "goal_admission_candidates": (
            None if goal_admission_service is None else goal_admission_service.get_candidate_snapshot()
        ),
        "world": world_state.model_dump(mode="json"),
        "autobio": deduplicate_entries(autobio_entries),
        "mac_console_status": mac_console_status,
    }


def build_memory_payload(target_app: FastAPI) -> dict[str, Any]:
    memory_service = target_app.state.memory_service
    return {
        "summary": memory_service.get_memory_summary(),
        "relationship": memory_service.get_relationship_summary(),
        "timeline": memory_service.get_memory_timeline(limit=40),
    }


def build_persona_payload(target_app: FastAPI) -> dict[str, Any]:
    persona_service = target_app.state.persona_service
    return {
        "profile": persona_service.get_profile().model_dump(mode="json"),
        "emotion": persona_service.get_emotion_summary(),
    }


def build_app_snapshot(target_app: FastAPI) -> dict[str, Any]:
    return {
        "runtime": build_runtime_payload(target_app),
        "memory": build_memory_payload(target_app),
        "persona": build_persona_payload(target_app),
    }
