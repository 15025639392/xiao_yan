from __future__ import annotations

from typing import Any

from app.config import LLMProviderConfig, get_chat_provider, get_llm_provider_configs


def select_chat_provider_config() -> LLMProviderConfig:
    provider_catalog = get_llm_provider_configs()
    if not provider_catalog:
        raise RuntimeError("no llm provider is configured")

    provider_id = get_chat_provider()
    return next((item for item in provider_catalog if item.provider_id == provider_id), provider_catalog[0])


def build_gateway_init_kwargs(
    provider_config: LLMProviderConfig,
    *,
    model: str | None = None,
    http_client: Any = None,
) -> dict[str, Any]:
    return {
        "api_key": provider_config.api_key,
        "model": (model or provider_config.default_model).strip() or provider_config.default_model,
        "base_url": provider_config.base_url,
        "wire_api": provider_config.wire_api,
        "http_client": http_client,
    }
