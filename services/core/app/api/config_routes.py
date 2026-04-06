from __future__ import annotations

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.config import LLMProviderConfig, get_llm_provider_configs
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


class ConfigResponse(BaseModel):
    chat_context_limit: int
    chat_provider: str
    chat_model: str


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

    @router.get("/config")
    def get_config() -> ConfigResponse:
        config = get_runtime_config()
        return ConfigResponse(
            chat_context_limit=config.chat_context_limit,
            chat_provider=config.chat_provider,
            chat_model=config.chat_model,
        )

    @router.put("/config")
    def update_config(request: ConfigUpdateRequest) -> ConfigResponse:
        if request.chat_context_limit is None and request.chat_provider is None and request.chat_model is None:
            raise HTTPException(status_code=400, detail="at least one config field is required")

        config = get_runtime_config()
        provider_catalog = _provider_catalog_by_id()
        next_provider = config.chat_provider

        if request.chat_context_limit is not None:
            config.chat_context_limit = request.chat_context_limit
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
