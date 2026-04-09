from __future__ import annotations

from collections.abc import Generator

import httpx
from fastapi import Request

from app.config import get_chat_provider, get_llm_provider_configs
from app.goals.admission import GoalAdmissionService
from app.goals.repository import GoalRepository
from app.llm.gateway import ChatGateway
from app.memory.repository import MemoryRepository
from app.memory.service import MemoryService
from app.orchestrator.conversation_service import OrchestratorConversationService
from app.orchestrator.service import OrchestratorService
from app.persona.service import PersonaService
from app.planning.morning_plan import MorningPlanDraftGenerator, MorningPlanPlanner
from app.runtime import StateStore
from app.runtime_ext.bootstrap import ensure_runtime_initialized
from app.runtime_ext.runtime_config import get_runtime_config
from app.world.repository import WorldRepository
from app.world.service import WorldStateService


def get_persona_service(request: Request) -> PersonaService:
    ensure_runtime_initialized(request.app)
    return request.app.state.persona_service  # type: ignore[attr-defined]


def get_memory_service(request: Request) -> MemoryService:
    ensure_runtime_initialized(request.app)
    return request.app.state.memory_service  # type: ignore[attr-defined]


def get_chat_gateway() -> Generator[ChatGateway, None, None]:
    provider_catalog = get_llm_provider_configs()
    if not provider_catalog:
        raise RuntimeError("no llm provider is configured")

    runtime_config = get_runtime_config()
    runtime_provider = runtime_config.chat_provider
    selected_provider = next(
        (provider for provider in provider_catalog if provider.provider_id == runtime_provider),
        None,
    )
    if selected_provider is None:
        fallback_provider_id = get_chat_provider()
        selected_provider = next(
            (provider for provider in provider_catalog if provider.provider_id == fallback_provider_id),
            provider_catalog[0],
        )
        runtime_config.chat_provider = selected_provider.provider_id
        runtime_config.chat_model = selected_provider.default_model

    http_client = httpx.Client(timeout=httpx.Timeout(runtime_config.chat_read_timeout_seconds, connect=10.0))
    gateway = ChatGateway.from_provider_config(
        selected_provider,
        model=runtime_config.chat_model,
        http_client=http_client,
    )
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


def get_orchestrator_service(request: Request) -> OrchestratorService:
    ensure_runtime_initialized(request.app)
    return request.app.state.orchestrator_service


def get_orchestrator_conversation_service(request: Request) -> OrchestratorConversationService:
    ensure_runtime_initialized(request.app)
    return request.app.state.orchestrator_conversation_service


def get_goal_repository(request: Request) -> GoalRepository:
    ensure_runtime_initialized(request.app)
    return request.app.state.goal_repository


def get_goal_admission_service(request: Request) -> GoalAdmissionService:
    ensure_runtime_initialized(request.app)
    return request.app.state.goal_admission_service


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
