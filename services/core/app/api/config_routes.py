from __future__ import annotations

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from app.api.deps import get_goal_admission_service
from app.capabilities.file_policy import (
    FILE_MAX_LIST_ENTRIES_BOUNDS,
    FILE_MAX_READ_BYTES_BOUNDS,
    FILE_MAX_SEARCH_RESULTS_BOUNDS,
    FILE_MAX_WRITE_BYTES_BOUNDS,
)
from app.config import LLMProviderConfig, get_llm_provider_configs
from app.goals.admission import GoalAdmissionService
from app.llm.gateway import ChatGateway
from app.runtime_ext.bootstrap import reload_runtime
from app.runtime_ext.data_backup import (
    apply_testing_data_mode,
    create_data_backup_archive,
    get_data_environment_snapshot,
    import_data_backup_archive,
    is_testing_data_mode_enabled,
)
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
    chat_context_limit: int | None = Field(default=None, ge=1, le=20, description="聊天上下文轮次基线（1-20）")
    chat_provider: str | None = Field(default=None, min_length=1, description="聊天服务商标识，例如 openai/minimaxi/deepseek")
    chat_model: str | None = Field(default=None, min_length=1, description="聊天模型名称，例如 gpt-5.4")
    chat_read_timeout_seconds: int | None = Field(default=None, ge=10, le=600, description="聊天 read 超时（秒），默认 180")
    chat_continuous_reasoning_enabled: bool | None = Field(default=None, description="是否启用 chat 持续推理能力")
    chat_mcp_enabled: bool | None = Field(default=None, description="是否启用 chat MCP 工具")
    chat_mcp_servers: list[dict[str, object]] | None = Field(default=None, description="chat MCP server 配置列表")


class ChatMcpServerConfig(BaseModel):
    server_id: str = Field(..., min_length=1)
    command: str = Field(..., min_length=1)
    args: list[str] = Field(default_factory=list)
    cwd: str | None = None
    env: dict[str, str] = Field(default_factory=dict)
    enabled: bool = True
    timeout_seconds: int = Field(default=20, ge=1, le=120)


class ConfigResponse(BaseModel):
    chat_context_limit: int
    chat_provider: str
    chat_model: str
    chat_read_timeout_seconds: int
    chat_continuous_reasoning_enabled: bool = True
    chat_mcp_enabled: bool = False
    chat_mcp_servers: list[ChatMcpServerConfig] = Field(default_factory=list)


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


class CapabilityShellPolicyUpdateRequest(BaseModel):
    allowed_executables: list[str] | None = Field(default=None)
    allowed_git_subcommands: list[str] | None = Field(default=None)


class CapabilityShellPolicyResponse(BaseModel):
    version: str
    revision: int
    allowed_executables: list[str]
    allowed_git_subcommands: list[str]


class CapabilityShellPolicyHistoryItem(CapabilityShellPolicyResponse):
    source: str
    created_at: str


class CapabilityShellPolicyHistoryResponse(BaseModel):
    items: list[CapabilityShellPolicyHistoryItem]


class CapabilityFilePolicyUpdateRequest(BaseModel):
    max_read_bytes: int | None = Field(
        default=None,
        ge=FILE_MAX_READ_BYTES_BOUNDS[0],
        le=FILE_MAX_READ_BYTES_BOUNDS[1],
    )
    max_write_bytes: int | None = Field(
        default=None,
        ge=FILE_MAX_WRITE_BYTES_BOUNDS[0],
        le=FILE_MAX_WRITE_BYTES_BOUNDS[1],
    )
    max_search_results: int | None = Field(
        default=None,
        ge=FILE_MAX_SEARCH_RESULTS_BOUNDS[0],
        le=FILE_MAX_SEARCH_RESULTS_BOUNDS[1],
    )
    max_list_entries: int | None = Field(
        default=None,
        ge=FILE_MAX_LIST_ENTRIES_BOUNDS[0],
        le=FILE_MAX_LIST_ENTRIES_BOUNDS[1],
    )
    allowed_search_file_patterns: list[str] | None = Field(default=None)


class CapabilityFilePolicyResponse(BaseModel):
    version: str
    revision: int
    max_read_bytes: int
    max_write_bytes: int
    max_search_results: int
    max_list_entries: int
    allowed_search_file_patterns: list[str]


class CapabilityFilePolicyHistoryItem(CapabilityFilePolicyResponse):
    source: str
    created_at: str


class CapabilityFilePolicyHistoryResponse(BaseModel):
    items: list[CapabilityFilePolicyHistoryItem]


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


class DataEnvironmentResponse(BaseModel):
    testing_mode: bool
    mempalace_palace_path: str
    mempalace_wing: str
    mempalace_room: str
    default_backup_directory: str
    switch_backup_path: str | None = None


class DataEnvironmentUpdateRequest(BaseModel):
    testing_mode: bool
    backup_before_switch: bool = True


class DataBackupCreateRequest(BaseModel):
    backup_path: str | None = None


class DataBackupCreateResponse(BaseModel):
    backup_path: str
    created_at: str
    included_keys: list[str]


class DataBackupImportRequest(BaseModel):
    backup_path: str = Field(..., min_length=1)
    make_pre_import_backup: bool = True


class DataBackupImportResponse(BaseModel):
    imported_from: str
    restored_keys: list[str]
    pre_import_backup_path: str | None = None


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

    def _capability_shell_policy_response(payload: dict) -> CapabilityShellPolicyResponse:
        return CapabilityShellPolicyResponse.model_validate(payload)

    def _capability_file_policy_response(payload: dict) -> CapabilityFilePolicyResponse:
        return CapabilityFilePolicyResponse.model_validate(payload)

    def _data_environment_response(*, switch_backup_path: str | None = None) -> DataEnvironmentResponse:
        snapshot = get_data_environment_snapshot()
        return DataEnvironmentResponse(
            testing_mode=snapshot.testing_mode,
            mempalace_palace_path=snapshot.mempalace_palace_path,
            mempalace_wing=snapshot.mempalace_wing,
            mempalace_room=snapshot.mempalace_room,
            default_backup_directory=snapshot.default_backup_directory,
            switch_backup_path=switch_backup_path,
        )

    @router.get("/config")
    def get_config() -> ConfigResponse:
        config = get_runtime_config()
        return ConfigResponse(
            chat_context_limit=config.chat_context_limit,
            chat_provider=config.chat_provider,
            chat_model=config.chat_model,
            chat_read_timeout_seconds=config.chat_read_timeout_seconds,
            chat_continuous_reasoning_enabled=config.chat_continuous_reasoning_enabled,
            chat_mcp_enabled=config.chat_mcp_enabled,
            chat_mcp_servers=[ChatMcpServerConfig.model_validate(item) for item in config.list_chat_mcp_servers()],
        )

    @router.put("/config")
    def update_config(request: ConfigUpdateRequest) -> ConfigResponse:
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
        if request.chat_continuous_reasoning_enabled is not None:
            config.chat_continuous_reasoning_enabled = request.chat_continuous_reasoning_enabled
        if request.chat_mcp_enabled is not None:
            config.chat_mcp_enabled = request.chat_mcp_enabled
        if request.chat_mcp_servers is not None:
            try:
                normalized_servers = [ChatMcpServerConfig.model_validate(item).model_dump(mode="json") for item in request.chat_mcp_servers]
                config.replace_chat_mcp_servers(normalized_servers)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

        return ConfigResponse(
            chat_context_limit=config.chat_context_limit,
            chat_provider=next_provider,
            chat_model=config.chat_model,
            chat_read_timeout_seconds=config.chat_read_timeout_seconds,
            chat_continuous_reasoning_enabled=config.chat_continuous_reasoning_enabled,
            chat_mcp_enabled=config.chat_mcp_enabled,
            chat_mcp_servers=[ChatMcpServerConfig.model_validate(item) for item in config.list_chat_mcp_servers()],
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

    @router.get("/config/capabilities/shell-policy")
    def get_capability_shell_policy_config() -> CapabilityShellPolicyResponse:
        config = get_runtime_config()
        return _capability_shell_policy_response(config.get_capability_shell_policy())

    @router.put("/config/capabilities/shell-policy")
    def update_capability_shell_policy_config(
        request: CapabilityShellPolicyUpdateRequest,
    ) -> CapabilityShellPolicyResponse:
        if request.allowed_executables is None and request.allowed_git_subcommands is None:
            raise HTTPException(status_code=400, detail="at least one shell-policy field is required")
        config = get_runtime_config()
        try:
            updated = config.update_capability_shell_policy(
                allowed_executables=request.allowed_executables,
                allowed_git_subcommands=request.allowed_git_subcommands,
                source="api_update",
            )
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        return _capability_shell_policy_response(updated)

    @router.get("/config/capabilities/shell-policy/history")
    def get_capability_shell_policy_history(
        limit: int = Query(default=10, ge=1, le=50),
    ) -> CapabilityShellPolicyHistoryResponse:
        config = get_runtime_config()
        items = config.list_capability_shell_policy_history(limit=limit)
        return CapabilityShellPolicyHistoryResponse(
            items=[CapabilityShellPolicyHistoryItem.model_validate(item) for item in items],
        )

    @router.get("/config/capabilities/file-policy")
    def get_capability_file_policy_config() -> CapabilityFilePolicyResponse:
        config = get_runtime_config()
        return _capability_file_policy_response(config.get_capability_file_policy())

    @router.put("/config/capabilities/file-policy")
    def update_capability_file_policy_config(
        request: CapabilityFilePolicyUpdateRequest,
    ) -> CapabilityFilePolicyResponse:
        if (
            request.max_read_bytes is None
            and request.max_write_bytes is None
            and request.max_search_results is None
            and request.max_list_entries is None
            and request.allowed_search_file_patterns is None
        ):
            raise HTTPException(status_code=400, detail="at least one file-policy field is required")
        config = get_runtime_config()
        try:
            updated = config.update_capability_file_policy(
                max_read_bytes=request.max_read_bytes,
                max_write_bytes=request.max_write_bytes,
                max_search_results=request.max_search_results,
                max_list_entries=request.max_list_entries,
                allowed_search_file_patterns=request.allowed_search_file_patterns,
                source="api_update",
            )
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        return _capability_file_policy_response(updated)

    @router.get("/config/capabilities/file-policy/history")
    def get_capability_file_policy_history(
        limit: int = Query(default=10, ge=1, le=50),
    ) -> CapabilityFilePolicyHistoryResponse:
        config = get_runtime_config()
        items = config.list_capability_file_policy_history(limit=limit)
        return CapabilityFilePolicyHistoryResponse(
            items=[CapabilityFilePolicyHistoryItem.model_validate(item) for item in items],
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

    @router.get("/config/data-environment")
    def get_data_environment() -> DataEnvironmentResponse:
        return _data_environment_response()

    @router.put("/config/data-environment")
    def update_data_environment(
        request_body: DataEnvironmentUpdateRequest,
        request: Request,
    ) -> DataEnvironmentResponse:
        current_mode = is_testing_data_mode_enabled()
        if request_body.testing_mode == current_mode:
            return _data_environment_response()

        switch_backup_path: str | None = None
        if request_body.backup_before_switch:
            backup = create_data_backup_archive()
            switch_backup_path = backup.backup_path

        apply_testing_data_mode(request_body.testing_mode)
        reload_runtime(request.app)
        return _data_environment_response(switch_backup_path=switch_backup_path)

    @router.post("/config/data-backup")
    def create_data_backup(
        request_body: DataBackupCreateRequest,
    ) -> DataBackupCreateResponse:
        backup = create_data_backup_archive(request_body.backup_path)
        return DataBackupCreateResponse(
            backup_path=backup.backup_path,
            created_at=backup.created_at,
            included_keys=backup.restored_keys,
        )

    @router.post("/config/data-backup/import")
    def import_data_backup(
        request_body: DataBackupImportRequest,
        request: Request,
    ) -> DataBackupImportResponse:
        pre_import_backup_path: str | None = None
        if request_body.make_pre_import_backup:
            pre_import = create_data_backup_archive()
            pre_import_backup_path = pre_import.backup_path

        try:
            restored_keys = import_data_backup_archive(request_body.backup_path)
        except FileNotFoundError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

        reload_runtime(request.app)
        return DataBackupImportResponse(
            imported_from=request_body.backup_path,
            restored_keys=restored_keys,
            pre_import_backup_path=pre_import_backup_path,
        )

    return router
