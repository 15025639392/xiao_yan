from __future__ import annotations

from fastapi import HTTPException

from app.api.config_route_models import ChatModelProviderItem, ChatModelsResponse
from app.config import LLMProviderConfig


def build_chat_models_response(
    *,
    providers: list[LLMProviderConfig],
    current_provider: str,
    current_model: str,
    gateway_class,
) -> ChatModelsResponse:
    if not providers:
        raise HTTPException(status_code=503, detail="no llm provider configured")

    provider_items: list[ChatModelProviderItem] = []
    for provider in providers:
        models: list[str] = []
        seen_models: set[str] = set()
        error_message: str | None = None

        try:
            gateway = gateway_class.from_provider_config(provider)
            try:
                fetched_models = gateway.list_models()
            finally:
                gateway.close()
        except Exception as exception:  # noqa: BLE001
            fetched_models = []
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
        if provider.provider_id == current_provider and current_model and current_model not in seen_models:
            seen_models.add(current_model)
            models.insert(0, current_model)

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
        current_provider=current_provider,
        current_model=current_model,
    )
