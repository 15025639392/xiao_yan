from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request

from app.api.config_route_chat_models import build_chat_models_response
from app.api.config_route_handlers import (
    build_config_response,
    build_history_response,
    ensure_file_policy_patch,
    ensure_shell_policy_patch,
    update_file_policy,
    update_runtime_config,
    update_shell_policy,
)
from app.api.config_route_models import (
    CapabilityFilePolicyHistoryItem,
    CapabilityFilePolicyHistoryResponse,
    CapabilityFilePolicyResponse,
    CapabilityFilePolicyUpdateRequest,
    CapabilityShellPolicyHistoryItem,
    CapabilityShellPolicyHistoryResponse,
    CapabilityShellPolicyResponse,
    CapabilityShellPolicyUpdateRequest,
    ChatMcpServerConfig,
    ChatModelsResponse,
    ConfigResponse,
    ConfigUpdateRequest,
    DataBackupCreateRequest,
    DataBackupCreateResponse,
    DataBackupImportRequest,
    DataBackupImportResponse,
    DataEnvironmentResponse,
    DataEnvironmentUpdateRequest,
)
from app.config import LLMProviderConfig, get_llm_provider_configs
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

def build_config_router() -> APIRouter:
    router = APIRouter()

    def _provider_catalog_by_id() -> dict[str, LLMProviderConfig]:
        providers = get_llm_provider_configs()
        return {provider.provider_id: provider for provider in providers}

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
        return build_config_response(
            config,
            config_response_model=ConfigResponse,
            chat_mcp_server_model=ChatMcpServerConfig,
        )

    @router.put("/config")
    def update_config(request: ConfigUpdateRequest) -> ConfigResponse:
        config = get_runtime_config()
        provider_catalog = _provider_catalog_by_id()
        if request.chat_mcp_servers is not None:
            try:
                normalized_servers = [ChatMcpServerConfig.model_validate(item).model_dump(mode="json") for item in request.chat_mcp_servers]
                request = request.model_copy(update={"chat_mcp_servers": normalized_servers})
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
        next_provider = update_runtime_config(config, request=request, provider_catalog=provider_catalog)
        return build_config_response(
            config,
            config_response_model=ConfigResponse,
            chat_mcp_server_model=ChatMcpServerConfig,
            chat_provider=next_provider,
        )

    @router.get("/config/capabilities/shell-policy")
    def get_capability_shell_policy_config() -> CapabilityShellPolicyResponse:
        config = get_runtime_config()
        return _capability_shell_policy_response(config.get_capability_shell_policy())

    @router.put("/config/capabilities/shell-policy")
    def update_capability_shell_policy_config(
        request: CapabilityShellPolicyUpdateRequest,
    ) -> CapabilityShellPolicyResponse:
        ensure_shell_policy_patch(request)
        config = get_runtime_config()
        updated = update_shell_policy(config, request=request)
        return _capability_shell_policy_response(updated)

    @router.get("/config/capabilities/shell-policy/history")
    def get_capability_shell_policy_history(
        limit: int = Query(default=10, ge=1, le=50),
    ) -> CapabilityShellPolicyHistoryResponse:
        config = get_runtime_config()
        items = config.list_capability_shell_policy_history(limit=limit)
        return build_history_response(
            items=items,
            response_model=CapabilityShellPolicyHistoryResponse,
            item_model=CapabilityShellPolicyHistoryItem,
        )

    @router.get("/config/capabilities/file-policy")
    def get_capability_file_policy_config() -> CapabilityFilePolicyResponse:
        config = get_runtime_config()
        return _capability_file_policy_response(config.get_capability_file_policy())

    @router.put("/config/capabilities/file-policy")
    def update_capability_file_policy_config(
        request: CapabilityFilePolicyUpdateRequest,
    ) -> CapabilityFilePolicyResponse:
        ensure_file_policy_patch(request)
        config = get_runtime_config()
        updated = update_file_policy(config, request=request)
        return _capability_file_policy_response(updated)

    @router.get("/config/capabilities/file-policy/history")
    def get_capability_file_policy_history(
        limit: int = Query(default=10, ge=1, le=50),
    ) -> CapabilityFilePolicyHistoryResponse:
        config = get_runtime_config()
        items = config.list_capability_file_policy_history(limit=limit)
        return build_history_response(
            items=items,
            response_model=CapabilityFilePolicyHistoryResponse,
            item_model=CapabilityFilePolicyHistoryItem,
        )

    @router.get("/config/chat-models")
    def get_chat_models() -> ChatModelsResponse:
        config = get_runtime_config()
        providers = get_llm_provider_configs()
        return build_chat_models_response(
            providers=providers,
            current_provider=config.chat_provider,
            current_model=config.chat_model,
            gateway_class=ChatGateway,
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
