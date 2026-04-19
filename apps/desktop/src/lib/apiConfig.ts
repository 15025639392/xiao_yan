import { get, post, put } from "./apiClient";

export type AppConfig = {
  chat_context_limit: number;
  chat_provider: string;
  chat_model: string;
  chat_read_timeout_seconds: number;
  chat_continuous_reasoning_enabled: boolean;
  chat_mcp_enabled: boolean;
  chat_mcp_servers: ChatMcpServerConfig[];
};

export type ChatMcpServerConfig = {
  server_id: string;
  command: string;
  args: string[];
  cwd?: string | null;
  env: Record<string, string>;
  enabled: boolean;
  timeout_seconds: number;
};

export type DataEnvironmentStatus = {
  testing_mode: boolean;
  mempalace_palace_path: string;
  mempalace_wing: string;
  mempalace_room: string;
  default_backup_directory: string;
  switch_backup_path?: string | null;
};

export type DataEnvironmentUpdatePayload = {
  testing_mode: boolean;
  backup_before_switch?: boolean;
};

export type DataBackupCreatePayload = {
  backup_path?: string | null;
};

export type DataBackupCreateResponse = {
  backup_path: string;
  created_at: string;
  included_keys: string[];
};

export type DataBackupImportPayload = {
  backup_path: string;
  make_pre_import_backup?: boolean;
};

export type DataBackupImportResponse = {
  imported_from: string;
  restored_keys: string[];
  pre_import_backup_path?: string | null;
};

export type ChatModelProviderItem = {
  provider_id: string;
  provider_name: string;
  models: string[];
  default_model: string;
  error?: string | null;
};

export type ChatModelsResponse = {
  providers: ChatModelProviderItem[];
  current_provider: string;
  current_model: string;
};

export const DEFAULT_CHAT_PROVIDER = "openai";
export const DEFAULT_CHAT_MODEL = "gpt-5.4";

function normalizeAppConfig(payload: Partial<AppConfig> | null | undefined): AppConfig {
  const source = payload ?? {};
  const rawMcpServers = Array.isArray(source.chat_mcp_servers) ? source.chat_mcp_servers : [];
  const normalizedMcpServers: ChatMcpServerConfig[] = rawMcpServers
    .map((item) => {
      if (!item || typeof item !== "object") return null;
      const candidate = item as Partial<ChatMcpServerConfig>;
      if (typeof candidate.server_id !== "string" || !candidate.server_id.trim()) return null;
      if (typeof candidate.command !== "string" || !candidate.command.trim()) return null;
      return {
        server_id: candidate.server_id.trim(),
        command: candidate.command.trim(),
        args: Array.isArray(candidate.args) ? candidate.args.filter((arg): arg is string => typeof arg === "string") : [],
        cwd: typeof candidate.cwd === "string" ? candidate.cwd : null,
        env:
          candidate.env && typeof candidate.env === "object"
            ? Object.fromEntries(
                Object.entries(candidate.env).filter(
                  (entry): entry is [string, string] => typeof entry[0] === "string" && typeof entry[1] === "string",
                ),
              )
            : {},
        enabled: typeof candidate.enabled === "boolean" ? candidate.enabled : true,
        timeout_seconds:
          typeof candidate.timeout_seconds === "number" && Number.isFinite(candidate.timeout_seconds)
            ? Math.max(1, Math.min(120, Math.floor(candidate.timeout_seconds)))
            : 20,
      };
    })
    .filter((item): item is ChatMcpServerConfig => item !== null);

  return {
    chat_context_limit: typeof source.chat_context_limit === "number" ? source.chat_context_limit : 6,
    chat_provider:
      typeof source.chat_provider === "string" && source.chat_provider.trim()
        ? source.chat_provider.trim()
        : DEFAULT_CHAT_PROVIDER,
    chat_model:
      typeof source.chat_model === "string" && source.chat_model.trim() ? source.chat_model.trim() : DEFAULT_CHAT_MODEL,
    chat_read_timeout_seconds:
      typeof source.chat_read_timeout_seconds === "number" ? source.chat_read_timeout_seconds : 180,
    chat_continuous_reasoning_enabled:
      typeof source.chat_continuous_reasoning_enabled === "boolean" ? source.chat_continuous_reasoning_enabled : true,
    chat_mcp_enabled: typeof source.chat_mcp_enabled === "boolean" ? source.chat_mcp_enabled : false,
    chat_mcp_servers: normalizedMcpServers,
  };
}

export async function fetchConfig(): Promise<AppConfig> {
  const payload = await get<Partial<AppConfig>>("/config");
  return normalizeAppConfig(payload);
}

export async function updateConfig(data: Partial<AppConfig>): Promise<AppConfig> {
  const payload = await put<Partial<AppConfig>>("/config", data);
  return normalizeAppConfig(payload);
}

export function fetchChatModels(): Promise<ChatModelsResponse> {
  return get<ChatModelsResponse>("/config/chat-models");
}

export function fetchDataEnvironmentStatus(): Promise<DataEnvironmentStatus> {
  return get<DataEnvironmentStatus>("/config/data-environment");
}

export function updateDataEnvironmentStatus(
  payload: DataEnvironmentUpdatePayload,
): Promise<DataEnvironmentStatus> {
  return put<DataEnvironmentStatus>("/config/data-environment", payload);
}

export function createDataBackup(
  payload: DataBackupCreatePayload = {},
): Promise<DataBackupCreateResponse> {
  return post<DataBackupCreateResponse>("/config/data-backup", payload);
}

export function importDataBackup(
  payload: DataBackupImportPayload,
): Promise<DataBackupImportResponse> {
  return post<DataBackupImportResponse>("/config/data-backup/import", payload);
}
