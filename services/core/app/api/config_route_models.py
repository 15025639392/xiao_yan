from __future__ import annotations

from pydantic import BaseModel, Field

from app.capabilities.file_policy import (
    FILE_MAX_LIST_ENTRIES_BOUNDS,
    FILE_MAX_READ_BYTES_BOUNDS,
    FILE_MAX_SEARCH_RESULTS_BOUNDS,
    FILE_MAX_WRITE_BYTES_BOUNDS,
)


class ConfigUpdateRequest(BaseModel):
    chat_context_limit: int | None = Field(default=None, ge=1, le=20, description="聊天记忆预算基线（1-20），会映射为近期对话预算与长期检索命中数")
    chat_provider: str | None = Field(default=None, min_length=1, description="聊天服务商标识，例如 openai/minimaxi/deepseek")
    chat_model: str | None = Field(default=None, min_length=1, description="聊天模型名称，例如 gpt-5.4")
    chat_read_timeout_seconds: int | None = Field(default=None, ge=10, le=600, description="上游聊天模型读取超时（秒），默认 180")
    chat_continuous_reasoning_enabled: bool | None = Field(default=None, description="是否启用 chat reasoning session 机制（用于状态追踪与续写衔接）")
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
    max_read_bytes: int | None = Field(default=None, ge=FILE_MAX_READ_BYTES_BOUNDS[0], le=FILE_MAX_READ_BYTES_BOUNDS[1])
    max_write_bytes: int | None = Field(default=None, ge=FILE_MAX_WRITE_BYTES_BOUNDS[0], le=FILE_MAX_WRITE_BYTES_BOUNDS[1])
    max_search_results: int | None = Field(default=None, ge=FILE_MAX_SEARCH_RESULTS_BOUNDS[0], le=FILE_MAX_SEARCH_RESULTS_BOUNDS[1])
    max_list_entries: int | None = Field(default=None, ge=FILE_MAX_LIST_ENTRIES_BOUNDS[0], le=FILE_MAX_LIST_ENTRIES_BOUNDS[1])
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
