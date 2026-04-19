from __future__ import annotations

import os
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class LLMProviderConfig:
    provider_id: str
    provider_name: str
    api_key: str
    base_url: str
    wire_api: str
    default_model: str


def is_minimax_like_base_url(base_url: str) -> bool:
    normalized = base_url.lower()
    return "minimaxi.com" in normalized or "minimax.chat" in normalized or "minimax" in normalized


def is_deepseek_like_base_url(base_url: str) -> bool:
    normalized = base_url.lower()
    return "api.deepseek.com" in normalized or "deepseek.com" in normalized


def normalize_provider_id(provider_id: str) -> str:
    normalized = provider_id.strip().lower()
    normalized = re.sub(r"[^a-z0-9_-]+", "-", normalized)
    normalized = re.sub(r"-{2,}", "-", normalized)
    return normalized.strip("-")


def infer_wire_api(base_url: str, configured: str | None) -> str:
    if configured and configured.strip():
        return configured.strip()
    if is_minimax_like_base_url(base_url) or is_deepseek_like_base_url(base_url):
        return "chat"
    return "responses"


def normalize_minimax_model_name(model: str) -> str:
    normalized = model.strip()
    if normalized.lower().startswith("codex-"):
        normalized = normalized[6:].strip()
    return normalized


def get_llm_provider_configs() -> list[LLMProviderConfig]:
    providers: list[LLMProviderConfig] = []
    seen_provider_ids: set[str] = set()

    def register_provider(
        *,
        provider_id: str,
        provider_name: str,
        api_key: str,
        base_url: str,
        wire_api: str,
        default_model: str,
    ) -> None:
        normalized_provider_id = normalize_provider_id(provider_id)
        if not normalized_provider_id or normalized_provider_id in seen_provider_ids:
            return
        normalized_api_key = api_key.strip()
        normalized_base_url = base_url.strip().rstrip("/")
        normalized_default_model = default_model.strip()
        if not normalized_api_key or not normalized_base_url:
            return
        seen_provider_ids.add(normalized_provider_id)
        providers.append(
            LLMProviderConfig(
                provider_id=normalized_provider_id,
                provider_name=provider_name.strip() or normalized_provider_id,
                api_key=normalized_api_key,
                base_url=normalized_base_url,
                wire_api=wire_api.strip() or infer_wire_api(normalized_base_url, None),
                default_model=normalized_default_model or "gpt-5.4",
            )
        )

    openai_base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").strip()
    openai_model = os.getenv("OPENAI_MODEL", "gpt-5.4").strip() or "gpt-5.4"
    openai_api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if openai_api_key:
        register_provider(
            provider_id="openai",
            provider_name="OpenAI",
            api_key=openai_api_key,
            base_url=openai_base_url or "https://api.openai.com/v1",
            wire_api=infer_wire_api(openai_base_url or "https://api.openai.com/v1", os.getenv("OPENAI_WIRE_API")),
            default_model=openai_model,
        )

    minimax_api_key = os.getenv("MINIMAX_API_KEY", "").strip()
    minimax_base_url = os.getenv("MINIMAX_BASE_URL", "").strip()
    if not minimax_base_url:
        minimax_base_url = openai_base_url if is_minimax_like_base_url(openai_base_url) else "https://api.minimaxi.com/v1"
    minimax_wire_api_env = os.getenv("MINIMAX_WIRE_API")
    if minimax_wire_api_env is None and is_minimax_like_base_url(openai_base_url):
        minimax_wire_api_env = os.getenv("OPENAI_WIRE_API")
    minimax_model = os.getenv("MINIMAX_MODEL", "").strip()
    if not minimax_model and is_minimax_like_base_url(openai_base_url):
        minimax_model = openai_model
    if not minimax_model:
        minimax_model = "MiniMax-M2.7"
    minimax_model = normalize_minimax_model_name(minimax_model)
    if minimax_api_key:
        register_provider(
            provider_id="minimaxi",
            provider_name="MiniMax",
            api_key=minimax_api_key,
            base_url=minimax_base_url,
            wire_api=infer_wire_api(minimax_base_url, minimax_wire_api_env),
            default_model=minimax_model,
        )

    deepseek_api_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
    deepseek_base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com").strip()
    deepseek_model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat").strip() or "deepseek-chat"
    deepseek_wire_api = os.getenv("DEEPSEEK_WIRE_API")
    if deepseek_wire_api is None:
        deepseek_wire_api = "chat"
    if deepseek_api_key:
        register_provider(
            provider_id="deepseek",
            provider_name="DeepSeek",
            api_key=deepseek_api_key,
            base_url=deepseek_base_url or "https://api.deepseek.com",
            wire_api=infer_wire_api(deepseek_base_url or "https://api.deepseek.com", deepseek_wire_api),
            default_model=deepseek_model,
        )

    custom_provider_ids = os.getenv("LLM_PROVIDER_IDS", "")
    for raw_provider_id in custom_provider_ids.split(","):
        provider_id = normalize_provider_id(raw_provider_id)
        if not provider_id:
            continue
        env_token = provider_id.upper().replace("-", "_")
        provider_api_key = os.getenv(f"LLM_PROVIDER_{env_token}_API_KEY", "").strip()
        provider_base_url = os.getenv(f"LLM_PROVIDER_{env_token}_BASE_URL", "").strip()
        if not provider_api_key or not provider_base_url:
            continue
        register_provider(
            provider_id=provider_id,
            provider_name=os.getenv(f"LLM_PROVIDER_{env_token}_NAME", provider_id),
            api_key=provider_api_key,
            base_url=provider_base_url,
            wire_api=infer_wire_api(provider_base_url, os.getenv(f"LLM_PROVIDER_{env_token}_WIRE_API")),
            default_model=os.getenv(f"LLM_PROVIDER_{env_token}_MODEL", "gpt-5.4"),
        )

    return providers


def get_chat_provider() -> str:
    provider_catalog = get_llm_provider_configs()
    if not provider_catalog:
        return "openai"

    configured_provider = normalize_provider_id(os.getenv("CHAT_PROVIDER", ""))
    if configured_provider and any(provider.provider_id == configured_provider for provider in provider_catalog):
        return configured_provider

    if any(provider.provider_id == "openai" for provider in provider_catalog):
        return "openai"
    return provider_catalog[0].provider_id


def get_chat_model() -> str:
    configured = os.getenv("CHAT_MODEL", "").strip()
    if configured:
        current_provider = get_chat_provider()
        if current_provider == "minimaxi":
            return normalize_minimax_model_name(configured)
        return configured

    current_provider = get_chat_provider()
    for provider in get_llm_provider_configs():
        if provider.provider_id == current_provider:
            return provider.default_model

    fallback_model = os.getenv("OPENAI_MODEL", "").strip()
    return fallback_model or "gpt-5.4"
