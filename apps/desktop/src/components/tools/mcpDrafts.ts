import type { ChatMcpServerConfig } from "../../lib/api";

export type McpServerDraft = {
  server_id: string;
  command: string;
  argsText: string;
  cwd: string;
  envText: string;
  enabled: boolean;
  timeout_seconds: number;
};

export const EMPTY_MCP_SERVER_DRAFT: McpServerDraft = {
  server_id: "",
  command: "",
  argsText: "",
  cwd: "",
  envText: "",
  enabled: true,
  timeout_seconds: 20,
};

export function toMcpDraft(server: ChatMcpServerConfig): McpServerDraft {
  return {
    server_id: server.server_id,
    command: server.command,
    argsText: server.args.join("\n"),
    cwd: server.cwd ?? "",
    envText: Object.entries(server.env)
      .map(([key, value]) => `${key}=${value}`)
      .join("\n"),
    enabled: server.enabled,
    timeout_seconds: server.timeout_seconds,
  };
}

export function parseMcpServerDraft(draft: McpServerDraft): { server: ChatMcpServerConfig | null; error: string | null } {
  const serverId = draft.server_id.trim().toLowerCase();
  const command = draft.command.trim();

  if (!serverId) {
    return { server: null, error: "MCP Server ID 不能为空" };
  }
  if (!command) {
    return { server: null, error: "MCP command 不能为空" };
  }

  const args = draft.argsText
    .split("\n")
    .map((item) => item.trim())
    .filter((item) => item.length > 0);

  const env: Record<string, string> = {};
  const envLines = draft.envText
    .split("\n")
    .map((item) => item.trim())
    .filter((item) => item.length > 0);

  for (const line of envLines) {
    const splitIndex = line.indexOf("=");
    if (splitIndex <= 0) {
      return { server: null, error: `环境变量格式错误: ${line}（应为 KEY=VALUE）` };
    }
    const key = line.slice(0, splitIndex).trim();
    const value = line.slice(splitIndex + 1);
    if (!key) {
      return { server: null, error: `环境变量 key 不能为空: ${line}` };
    }
    env[key] = value;
  }

  const timeout = Number.isFinite(draft.timeout_seconds) ? Math.floor(draft.timeout_seconds) : 20;
  return {
    server: {
      server_id: serverId,
      command,
      args,
      cwd: draft.cwd.trim() || null,
      env,
      enabled: draft.enabled,
      timeout_seconds: Math.max(1, Math.min(120, timeout)),
    },
    error: null,
  };
}
