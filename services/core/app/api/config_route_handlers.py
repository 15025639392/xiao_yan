from __future__ import annotations

from fastapi import HTTPException

from app.config import LLMProviderConfig
from app.runtime_ext.runtime_config import RuntimeConfig


def build_config_response(
    config: RuntimeConfig,
    *,
    config_response_model,
    chat_mcp_server_model,
    chat_provider: str | None = None,
):
    return config_response_model(
        chat_context_limit=config.chat_context_limit,
        chat_provider=chat_provider or config.chat_provider,
        chat_model=config.chat_model,
        chat_read_timeout_seconds=config.chat_read_timeout_seconds,
        chat_continuous_reasoning_enabled=config.chat_continuous_reasoning_enabled,
        chat_mcp_enabled=config.chat_mcp_enabled,
        chat_mcp_servers=[chat_mcp_server_model.model_validate(item) for item in config.list_chat_mcp_servers()],
    )


def update_runtime_config(
    config: RuntimeConfig,
    *,
    request,
    provider_catalog: dict[str, LLMProviderConfig],
) -> str:
    if (
        request.chat_context_limit is None
        and request.chat_provider is None
        and request.chat_model is None
        and request.chat_read_timeout_seconds is None
        and request.chat_continuous_reasoning_enabled is None
        and request.chat_mcp_enabled is None
        and request.chat_mcp_servers is None
    ):
        raise HTTPException(status_code=400, detail="at least one config field is required")

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
    if request.chat_continuous_reasoning_enabled is not None:
        config.chat_continuous_reasoning_enabled = request.chat_continuous_reasoning_enabled
    if request.chat_mcp_enabled is not None:
        config.chat_mcp_enabled = request.chat_mcp_enabled
    if request.chat_mcp_servers is not None:
        try:
            config.replace_chat_mcp_servers(list(request.chat_mcp_servers))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    return next_provider


def ensure_shell_policy_patch(request) -> None:
    if request.allowed_executables is None and request.allowed_git_subcommands is None:
        raise HTTPException(status_code=400, detail="at least one shell-policy field is required")


def ensure_file_policy_patch(request) -> None:
    if (
        request.max_read_bytes is None
        and request.max_write_bytes is None
        and request.max_search_results is None
        and request.max_list_entries is None
        and request.allowed_search_file_patterns is None
    ):
        raise HTTPException(status_code=400, detail="at least one file-policy field is required")


def update_shell_policy(config: RuntimeConfig, *, request):
    try:
        return config.update_capability_shell_policy(
            allowed_executables=request.allowed_executables,
            allowed_git_subcommands=request.allowed_git_subcommands,
            source="api_update",
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


def update_file_policy(config: RuntimeConfig, *, request):
    try:
        return config.update_capability_file_policy(
            max_read_bytes=request.max_read_bytes,
            max_write_bytes=request.max_write_bytes,
            max_search_results=request.max_search_results,
            max_list_entries=request.max_list_entries,
            allowed_search_file_patterns=request.allowed_search_file_patterns,
            source="api_update",
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


def build_history_response(*, items: list[dict], response_model, item_model):
    return response_model(items=[item_model.model_validate(item) for item in items])
