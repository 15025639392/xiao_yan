from __future__ import annotations

from collections.abc import Generator

from fastapi import Request

from app.goals.repository import GoalRepository
from app.llm.gateway import ChatGateway
from app.memory.repository import MemoryRepository
from app.memory.service import MemoryService
from app.persona.service import PersonaService
from app.planning.morning_plan import MorningPlanDraftGenerator, MorningPlanPlanner
from app.runtime import StateStore
from app.runtime_ext.bootstrap import ensure_runtime_initialized
from app.world.repository import WorldRepository
from app.world.service import WorldStateService


def get_persona_service(request: Request) -> PersonaService:
    ensure_runtime_initialized(request.app)
    return request.app.state.persona_service  # type: ignore[attr-defined]


def get_memory_service(request: Request) -> MemoryService:
    ensure_runtime_initialized(request.app)
    return request.app.state.memory_service  # type: ignore[attr-defined]


def get_chat_gateway() -> Generator[ChatGateway, None, None]:
    gateway = ChatGateway.from_env()
    try:
        yield gateway
    finally:
        gateway.close()


def get_memory_repository(request: Request) -> MemoryRepository:
    ensure_runtime_initialized(request.app)
    return request.app.state.memory_repository


def get_state_store(request: Request) -> StateStore:
    ensure_runtime_initialized(request.app)
    return request.app.state.state_store


def get_goal_repository(request: Request) -> GoalRepository:
    ensure_runtime_initialized(request.app)
    return request.app.state.goal_repository


def get_world_repository(request: Request) -> WorldRepository:
    ensure_runtime_initialized(request.app)
    return request.app.state.world_repository


def get_world_state_service() -> WorldStateService:
    return WorldStateService()


def get_morning_plan_planner() -> MorningPlanPlanner:
    return MorningPlanPlanner()


def get_morning_plan_draft_generator() -> Generator[MorningPlanDraftGenerator | None, None, None]:
    from app.config import is_morning_plan_llm_enabled
    from app.planning.morning_plan import LLMMorningPlanDraftGenerator

    if not is_morning_plan_llm_enabled():
        yield None
        return

    try:
        gateway = ChatGateway.from_env()
    except RuntimeError:
        yield None
        return

    try:
        yield LLMMorningPlanDraftGenerator(gateway)
    finally:
        gateway.close()
