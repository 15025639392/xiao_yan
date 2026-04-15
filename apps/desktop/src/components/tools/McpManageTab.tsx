import { useEffect, useState } from "react";
import type { AppConfig, ChatMcpServerConfig } from "../../lib/api";
import { fetchConfig, updateConfig } from "../../lib/api";

type McpServerDraft = {
  server_id: string;
  command: string;
  argsText: string;
  cwd: string;
  envText: string;
  enabled: boolean;
  timeout_seconds: number;
};

const EMPTY_MCP_SERVER_DRAFT: McpServerDraft = {
  server_id: "",
  command: "",
  argsText: "",
  cwd: "",
  envText: "",
  enabled: true,
  timeout_seconds: 20,
};

function toMcpDraft(server: ChatMcpServerConfig): McpServerDraft {
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

function parseMcpServerDraft(draft: McpServerDraft): { server: ChatMcpServerConfig | null; error: string | null } {
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

export function McpManageTab() {
  const [config, setConfig] = useState<AppConfig | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState("");
  const [formError, setFormError] = useState("");
  const [mcpDraft, setMcpDraft] = useState<McpServerDraft>(EMPTY_MCP_SERVER_DRAFT);
  const [mcpEditingServerId, setMcpEditingServerId] = useState<string | null>(null);
  const [mcpFormVisible, setMcpFormVisible] = useState(false);

  useEffect(() => {
    setIsLoading(true);
    setError("");
    fetchConfig()
      .then((payload) => setConfig(payload))
      .catch((loadError) => {
        setError(loadError instanceof Error ? loadError.message : "加载 MCP 配置失败");
      })
      .finally(() => {
        setIsLoading(false);
      });
  }, []);

  async function commitUpdate(patch: Partial<AppConfig>) {
    setIsSaving(true);
    setError("");
    try {
      const updated = await updateConfig(patch);
      setConfig(updated);
      return updated;
    } catch (updateError) {
      const message = updateError instanceof Error ? updateError.message : "保存 MCP 配置失败";
      setError(message);
      throw new Error(message);
    } finally {
      setIsSaving(false);
    }
  }

  function resetMcpForm() {
    setMcpDraft(EMPTY_MCP_SERVER_DRAFT);
    setMcpEditingServerId(null);
    setFormError("");
    setMcpFormVisible(false);
  }

  function startAddMcpServer() {
    setMcpEditingServerId(null);
    setMcpDraft(EMPTY_MCP_SERVER_DRAFT);
    setFormError("");
    setMcpFormVisible(true);
  }

  function startEditMcpServer(server: ChatMcpServerConfig) {
    setMcpEditingServerId(server.server_id);
    setMcpDraft(toMcpDraft(server));
    setFormError("");
    setMcpFormVisible(true);
  }

  async function handleSaveMcpServer() {
    if (!config) {
      return;
    }

    const parsed = parseMcpServerDraft(mcpDraft);
    if (!parsed.server) {
      setFormError(parsed.error ?? "MCP 配置无效");
      return;
    }

    const nextServer = parsed.server;
    const mcpServers = Array.isArray(config.chat_mcp_servers) ? config.chat_mcp_servers : [];
    const existingServerIdSet = new Set(mcpServers.map((item) => item.server_id));

    let nextServers: ChatMcpServerConfig[] = [];
    if (mcpEditingServerId) {
      if (!existingServerIdSet.has(mcpEditingServerId)) {
        setFormError(`找不到待编辑的 MCP Server：${mcpEditingServerId}`);
        return;
      }
      if (nextServer.server_id !== mcpEditingServerId && existingServerIdSet.has(nextServer.server_id)) {
        setFormError(`MCP Server ID 已存在：${nextServer.server_id}`);
        return;
      }
      nextServers = mcpServers.map((item) => (item.server_id === mcpEditingServerId ? nextServer : item));
    } else {
      if (existingServerIdSet.has(nextServer.server_id)) {
        setFormError(`MCP Server ID 已存在：${nextServer.server_id}`);
        return;
      }
      nextServers = [...mcpServers, nextServer];
    }

    try {
      await commitUpdate({ chat_mcp_servers: nextServers });
      resetMcpForm();
    } catch {
      setFormError("保存 MCP Server 失败");
    }
  }

  async function handleRemoveMcpServer(serverId: string) {
    if (!config) {
      return;
    }

    const mcpServers = Array.isArray(config.chat_mcp_servers) ? config.chat_mcp_servers : [];
    const nextServers = mcpServers.filter((item) => item.server_id !== serverId);
    try {
      await commitUpdate({ chat_mcp_servers: nextServers });
      if (mcpEditingServerId === serverId) {
        resetMcpForm();
      }
    } catch {
      setFormError("删除 MCP Server 失败");
    }
  }

  async function handleToggleMcpEnabled(enabled: boolean) {
    await commitUpdate({ chat_mcp_enabled: enabled });
  }

  async function handleToggleMcpServerEnabled(serverId: string, enabled: boolean) {
    if (!config) {
      return;
    }

    const mcpServers = Array.isArray(config.chat_mcp_servers) ? config.chat_mcp_servers : [];
    const nextServers = mcpServers.map((item) =>
      item.server_id === serverId ? { ...item, enabled } : item,
    );
    await commitUpdate({ chat_mcp_servers: nextServers });
  }

  const mcpEnabled = Boolean(config?.chat_mcp_enabled);
  const mcpServers = config ? config.chat_mcp_servers : [];

  return (
    <div className="tool-mcp-tab">
      <div className="tool-config-card">
        <div className="tool-config-card__header">
          <div>
            <h4>MCP 管理</h4>
            <p>统一维护 chat 可用的 MCP Server 清单和全局启用状态。</p>
          </div>
          <label className="tool-config-switch" htmlFor="toolbox-mcp-enabled">
            <span>启用 MCP</span>
            <input
              id="toolbox-mcp-enabled"
              type="checkbox"
              checked={mcpEnabled}
              disabled={isLoading || isSaving || config === null}
              onChange={(event) => {
                void handleToggleMcpEnabled(event.target.checked);
              }}
            />
          </label>
        </div>

        <div className="tool-config-actions">
          <button type="button" className="tool-config-btn" onClick={startAddMcpServer} disabled={isLoading || isSaving || config === null}>
            新增 MCP Server
          </button>
          {mcpFormVisible ? (
            <button type="button" className="tool-config-btn" onClick={resetMcpForm} disabled={isSaving}>
              取消编辑
            </button>
          ) : null}
        </div>

        {isLoading ? <p className="tool-config-hint">加载 MCP 配置...</p> : null}
        {error ? <p className="tool-config-error">{error}</p> : null}

        {mcpFormVisible ? (
          <div className="tool-mcp-form">
            <label>
              <span>MCP Server ID</span>
              <input
                type="text"
                value={mcpDraft.server_id}
                disabled={isSaving}
                onChange={(event) => {
                  setMcpDraft((prev) => ({ ...prev, server_id: event.target.value }));
                }}
                placeholder="例如 filesystem"
              />
            </label>

            <label>
              <span>MCP Command</span>
              <input
                type="text"
                value={mcpDraft.command}
                disabled={isSaving}
                onChange={(event) => {
                  setMcpDraft((prev) => ({ ...prev, command: event.target.value }));
                }}
                placeholder="例如 npx"
              />
            </label>

            <label>
              <span>MCP Args（每行一个）</span>
              <textarea
                value={mcpDraft.argsText}
                disabled={isSaving}
                onChange={(event) => {
                  setMcpDraft((prev) => ({ ...prev, argsText: event.target.value }));
                }}
                placeholder={"-y\n@modelcontextprotocol/server-filesystem\n/tmp"}
              />
            </label>

            <label>
              <span>MCP CWD（可选）</span>
              <input
                type="text"
                value={mcpDraft.cwd}
                disabled={isSaving}
                onChange={(event) => {
                  setMcpDraft((prev) => ({ ...prev, cwd: event.target.value }));
                }}
                placeholder="例如 /Users/ldy/Desktop/map/ai"
              />
            </label>

            <label>
              <span>MCP Env（每行 KEY=VALUE）</span>
              <textarea
                value={mcpDraft.envText}
                disabled={isSaving}
                onChange={(event) => {
                  setMcpDraft((prev) => ({ ...prev, envText: event.target.value }));
                }}
                placeholder={"API_KEY=your-key\nBASE_URL=https://example.com"}
              />
            </label>

            <label>
              <span>MCP Timeout（秒）</span>
              <input
                type="number"
                min={1}
                max={120}
                value={mcpDraft.timeout_seconds}
                disabled={isSaving}
                onChange={(event) => {
                  const nextValue = Number.parseInt(event.target.value, 10);
                  setMcpDraft((prev) => ({
                    ...prev,
                    timeout_seconds: Number.isFinite(nextValue) ? nextValue : prev.timeout_seconds,
                  }));
                }}
              />
            </label>

            <label className="tool-config-switch tool-config-switch--compact" htmlFor="toolbox-mcp-default-enabled">
              <span>默认启用</span>
              <input
                id="toolbox-mcp-default-enabled"
                type="checkbox"
                checked={mcpDraft.enabled}
                disabled={isSaving}
                onChange={(event) => {
                  setMcpDraft((prev) => ({ ...prev, enabled: event.target.checked }));
                }}
              />
            </label>

            <div className="tool-config-actions">
              <button
                type="button"
                className="tool-config-btn tool-config-btn--primary"
                disabled={isSaving}
                onClick={() => {
                  void handleSaveMcpServer();
                }}
              >
                保存 MCP Server
              </button>
            </div>

            {formError ? <p className="tool-config-error">{formError}</p> : null}
          </div>
        ) : null}

        {mcpServers.length === 0 ? (
          <p className="tool-config-hint">当前没有配置 MCP Server。</p>
        ) : (
          <div className="tool-mcp-list">
            {mcpServers.map((server) => (
              <div key={server.server_id} className="tool-mcp-item">
                <div className="tool-mcp-item__main">
                  <strong>{server.server_id}</strong>
                  <span>
                    {server.command} {server.args.join(" ")}
                  </span>
                  <code>
                    timeout: {server.timeout_seconds}s
                    {server.cwd ? ` · cwd: ${server.cwd}` : ""}
                  </code>
                </div>
                <div className="tool-mcp-item__actions">
                  <label className="tool-config-switch tool-config-switch--compact">
                    <span>启用</span>
                    <input
                      type="checkbox"
                      checked={server.enabled}
                      disabled={isSaving}
                      onChange={(event) => {
                        void handleToggleMcpServerEnabled(server.server_id, event.target.checked);
                      }}
                    />
                  </label>
                  <button type="button" className="tool-config-btn" disabled={isSaving} onClick={() => startEditMcpServer(server)}>
                    编辑
                  </button>
                  <button
                    type="button"
                    className="tool-config-btn tool-config-btn--danger"
                    disabled={isSaving}
                    onClick={() => {
                      void handleRemoveMcpServer(server.server_id);
                    }}
                  >
                    删除
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
