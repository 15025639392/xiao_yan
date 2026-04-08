from __future__ import annotations

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.api.deps import get_goal_admission_service
from app.config import LLMProviderConfig, get_llm_provider_configs
from app.goals.admission import GoalAdmissionService
from app.llm.gateway import ChatGateway
from app.runtime_ext.runtime_config import get_runtime_config

MINIMAX_FALLBACK_MODELS = [
    "MiniMax-M2.7",
    "MiniMax-M2.7-highspeed",
    "MiniMax-M2.5",
    "MiniMax-M2.5-highspeed",
    "MiniMax-M2.1",
    "MiniMax-M2.1-highspeed",
    "MiniMax-M2",
]


class ConfigUpdateRequest(BaseModel):
    chat_context_limit: int | None = Field(default=None, ge=1, le=20, description="聊天上下文相关事件数量限制（1-20）")
    chat_provider: str | None = Field(default=None, min_length=1, description="聊天服务商标识，例如 openai/minimaxi")
    chat_model: str | None = Field(default=None, min_length=1, description="聊天模型名称，例如 gpt-5.4")
    chat_read_timeout_seconds: int | None = Field(default=None, ge=10, le=600, description="聊天 read 超时（秒），默认 180")


class ConfigResponse(BaseModel):
    chat_context_limit: int
    chat_provider: str
    chat_model: str
    chat_read_timeout_seconds: int


class SelfProgrammingConfigUpdateRequest(BaseModel):
    hard_failure_cooldown_minutes: int | None = Field(default=None, ge=1, le=10080)
    proactive_cooldown_minutes: int | None = Field(default=None, ge=1, le=10080)


class SelfProgrammingConfigResponse(BaseModel):
    hard_failure_cooldown_minutes: int
    proactive_cooldown_minutes: int


class GoalAdmissionConfigUpdateRequest(BaseModel):
    stability_warning_rate: float | None = Field(default=None, ge=0.0, le=1.0)
    stability_danger_rate: float | None = Field(default=None, ge=0.0, le=1.0)
    user_topic_min_score: float | None = Field(default=None, ge=0.0, le=1.0)
    user_topic_defer_score: float | None = Field(default=None, ge=0.0, le=1.0)
    world_event_min_score: float | None = Field(default=None, ge=0.0, le=1.0)
    world_event_defer_score: float | None = Field(default=None, ge=0.0, le=1.0)
    chain_next_min_score: float | None = Field(default=None, ge=0.0, le=1.0)
    chain_next_defer_score: float | None = Field(default=None, ge=0.0, le=1.0)


class GoalAdmissionConfigResponse(BaseModel):
    stability_warning_rate: float
    stability_danger_rate: float
    user_topic_min_score: float
    user_topic_defer_score: float
    world_event_min_score: float
    world_event_defer_score: float
    chain_next_min_score: float
    chain_next_defer_score: float


class GoalAdmissionConfigHistoryItem(BaseModel):
    revision: int
    source: str
    stability_warning_rate: float
    stability_danger_rate: float
    user_topic_min_score: float
    user_topic_defer_score: float
    world_event_min_score: float
    world_event_defer_score: float
    chain_next_min_score: float
    chain_next_defer_score: float
    created_at: str
    rolled_back_from_revision: int | None = None


class GoalAdmissionConfigHistoryResponse(BaseModel):
    items: list[GoalAdmissionConfigHistoryItem]


class GoalAdmissionConfigRollbackResponse(GoalAdmissionConfigResponse):
    revision: int
    rolled_back_from_revision: int


class ChatModelProviderItem(BaseModel):
    provider_id: str
    provider_name: str
    models: list[str]
    default_model: str
    error: str | None = None


class ChatModelsResponse(BaseModel):
    providers: list[ChatModelProviderItem]
    current_provider: str
    current_model: str


def build_config_router() -> APIRouter:
    router = APIRouter()

    def _provider_catalog_by_id() -> dict[str, LLMProviderConfig]:
        providers = get_llm_provider_configs()
        return {provider.provider_id: provider for provider in providers}

    def _goal_admission_config_response(config) -> GoalAdmissionConfigResponse:
        return GoalAdmissionConfigResponse(
            stability_warning_rate=config.goal_admission_stability_warning_rate,
            stability_danger_rate=config.goal_admission_stability_danger_rate,
            user_topic_min_score=config.goal_admission_user_topic_min_score,
            user_topic_defer_score=config.goal_admission_user_topic_defer_score,
            world_event_min_score=config.goal_admission_world_event_min_score,
            world_event_defer_score=config.goal_admission_world_event_defer_score,
            chain_next_min_score=config.goal_admission_chain_next_min_score,
            chain_next_defer_score=config.goal_admission_chain_next_defer_score,
        )

    def _apply_thresholds_to_admission_service(payload: dict[str, float | int], service: GoalAdmissionService) -> None:
        service.min_score = float(payload["user_topic_min_score"])
        service.defer_score = float(payload["user_topic_defer_score"])
        service.world_min_score = float(payload["world_event_min_score"])
        service.world_defer_score = float(payload["world_event_defer_score"])
        service.chain_min_score = float(payload["chain_next_min_score"])
        service.chain_defer_score = float(payload["chain_next_defer_score"])

    @router.get("/config")
    def get_config() -> ConfigResponse:
        config = get_runtime_config()
        return ConfigResponse(
            chat_context_limit=config.chat_context_limit,
            chat_provider=config.chat_provider,
            chat_model=config.chat_model,
            chat_read_timeout_seconds=config.chat_read_timeout_seconds,
        )

    @router.get("/config/self-programming")
    def get_self_programming_config() -> SelfProgrammingConfigResponse:
        config = get_runtime_config()
        return SelfProgrammingConfigResponse(
            hard_failure_cooldown_minutes=config.self_programming_hard_failure_cooldown_minutes,
            proactive_cooldown_minutes=config.self_programming_proactive_cooldown_minutes,
        )

    @router.put("/config")
    def update_config(request: ConfigUpdateRequest) -> ConfigResponse:
        if (
            request.chat_context_limit is None
            and request.chat_provider is None
            and request.chat_model is None
            and request.chat_read_timeout_seconds is None
        ):
            raise HTTPException(status_code=400, detail="at least one config field is required")

        config = get_runtime_config()
        provider_catalog = _provider_catalog_by_id()
        next_provider = config.chat_provider

        if request.chat_context_limit is not None:
            config.chat_context_limit = request.chat_context_limit
        if request.chat_read_timeout_seconds is not None:
            config.chat_read_timeout_seconds = request.chat_read_timeout_seconds
        if request.chat_provider is not None:
            chat_provider = request.chat_provider.strip().lower()
            if not chat_provider:
                raise HTTPException(status_code=400, detail="chat_provider must not be empty")
            provider_config = provider_catalog.get(chat_provider)
            if provider_config is None:
                raise HTTPException(status_code=400, detail=f"unknown chat_provider: {chat_provider}")
            config.chat_provider = chat_provider
            next_provider = chat_provider
            if request.chat_model is None:
                config.chat_model = provider_config.default_model
        if request.chat_model is not None:
            chat_model = request.chat_model.strip()
            if not chat_model:
                raise HTTPException(status_code=400, detail="chat_model must not be empty")
            config.chat_model = chat_model

        return ConfigResponse(
            chat_context_limit=config.chat_context_limit,
            chat_provider=next_provider,
            chat_model=config.chat_model,
            chat_read_timeout_seconds=config.chat_read_timeout_seconds,
        )

    @router.put("/config/self-programming")
    def update_self_programming_config(
        request: SelfProgrammingConfigUpdateRequest,
    ) -> SelfProgrammingConfigResponse:
        if (
            request.hard_failure_cooldown_minutes is None
            and request.proactive_cooldown_minutes is None
        ):
            raise HTTPException(
                status_code=400,
                detail="at least one self-programming config field is required",
            )

        config = get_runtime_config()
        if request.hard_failure_cooldown_minutes is not None:
            config.self_programming_hard_failure_cooldown_minutes = request.hard_failure_cooldown_minutes
        if request.proactive_cooldown_minutes is not None:
            config.self_programming_proactive_cooldown_minutes = request.proactive_cooldown_minutes

        return SelfProgrammingConfigResponse(
            hard_failure_cooldown_minutes=config.self_programming_hard_failure_cooldown_minutes,
            proactive_cooldown_minutes=config.self_programming_proactive_cooldown_minutes,
        )

    @router.get("/config/goal-admission")
    def get_goal_admission_config() -> GoalAdmissionConfigResponse:
        config = get_runtime_config()
        return _goal_admission_config_response(config)

    @router.put("/config/goal-admission")
    def update_goal_admission_config(
        request: GoalAdmissionConfigUpdateRequest,
        admission_service: GoalAdmissionService = Depends(get_goal_admission_service),
    ) -> GoalAdmissionConfigResponse:
        if (
            request.stability_warning_rate is None
            and request.stability_danger_rate is None
            and request.user_topic_min_score is None
            and request.user_topic_defer_score is None
            and request.world_event_min_score is None
            and request.world_event_defer_score is None
            and request.chain_next_min_score is None
            and request.chain_next_defer_score is None
        ):
            raise HTTPException(
                status_code=400,
                detail="at least one goal-admission config field is required",
            )

        config = get_runtime_config()
        try:
            updated = config.update_goal_admission_thresholds(
                stability_warning_rate=request.stability_warning_rate,
                stability_danger_rate=request.stability_danger_rate,
                user_topic_min_score=request.user_topic_min_score,
                user_topic_defer_score=request.user_topic_defer_score,
                world_event_min_score=request.world_event_min_score,
                world_event_defer_score=request.world_event_defer_score,
                chain_next_min_score=request.chain_next_min_score,
                chain_next_defer_score=request.chain_next_defer_score,
                source="api_update",
            )
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

        _apply_thresholds_to_admission_service(updated, admission_service)
        return _goal_admission_config_response(config)

    @router.get("/config/goal-admission/history")
    def get_goal_admission_config_history(
        limit: int = Query(default=10, ge=1, le=50),
    ) -> GoalAdmissionConfigHistoryResponse:
        config = get_runtime_config()
        items = config.list_goal_admission_config_history(limit=limit)
        return GoalAdmissionConfigHistoryResponse(
            items=[GoalAdmissionConfigHistoryItem.model_validate(item) for item in items],
        )

    @router.post("/config/goal-admission/rollback")
    def rollback_goal_admission_config(
        admission_service: GoalAdmissionService = Depends(get_goal_admission_service),
    ) -> GoalAdmissionConfigRollbackResponse:
        config = get_runtime_config()
        try:
            rolled_back = config.rollback_goal_admission_thresholds()
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        _apply_thresholds_to_admission_service(rolled_back, admission_service)
        return GoalAdmissionConfigRollbackResponse(
            stability_warning_rate=float(rolled_back["stability_warning_rate"]),
            stability_danger_rate=float(rolled_back["stability_danger_rate"]),
            user_topic_min_score=float(rolled_back["user_topic_min_score"]),
            user_topic_defer_score=float(rolled_back["user_topic_defer_score"]),
            world_event_min_score=float(rolled_back["world_event_min_score"]),
            world_event_defer_score=float(rolled_back["world_event_defer_score"]),
            chain_next_min_score=float(rolled_back["chain_next_min_score"]),
            chain_next_defer_score=float(rolled_back["chain_next_defer_score"]),
            revision=int(rolled_back["revision"]),
            rolled_back_from_revision=int(rolled_back["rolled_back_from_revision"]),
        )

    @router.get("/config/chat-models")
    def get_chat_models() -> ChatModelsResponse:
        config = get_runtime_config()
        providers = get_llm_provider_configs()
        if not providers:
            raise HTTPException(status_code=503, detail="no llm provider configured")

        provider_items: list[ChatModelProviderItem] = []
        for provider in providers:
            models: list[str] = []
            seen_models: set[str] = set()
            error_message: str | None = None

            try:
                gateway = ChatGateway.from_provider_config(provider)
                try:
                    fetched_models = gateway.list_models()
                finally:
                    gateway.close()
            except Exception as exception:  # noqa: BLE001
                fetched_models = []
                if (
                    provider.provider_id == "minimaxi"
                    and isinstance(exception, httpx.HTTPStatusError)
                    and exception.response.status_code == 404
                ):
                    fetched_models = list(MINIMAX_FALLBACK_MODELS)
                else:
                    error_message = str(exception)

            for model in fetched_models:
                normalized = model.strip()
                if not normalized or normalized in seen_models:
                    continue
                seen_models.add(normalized)
                models.append(normalized)

            if provider.default_model and provider.default_model not in seen_models:
                seen_models.add(provider.default_model)
                models.append(provider.default_model)
            if (
                provider.provider_id == config.chat_provider
                and config.chat_model
                and config.chat_model not in seen_models
            ):
                seen_models.add(config.chat_model)
                models.insert(0, config.chat_model)

            provider_items.append(
                ChatModelProviderItem(
                    provider_id=provider.provider_id,
                    provider_name=provider.provider_name,
                    models=models,
                    default_model=provider.default_model,
                    error=error_message,
                )
            )

        return ChatModelsResponse(
            providers=provider_items,
            current_provider=config.chat_provider,
            current_model=config.chat_model,
        )

    return router
