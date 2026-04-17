import { useEffect, useState } from "react";
import type {
  AppConfig,
  ChatFolderPermission,
  ChatModelProviderItem,
  DataEnvironmentStatus,
  FolderAccessLevel,
} from "../../lib/api";
import { isTauriRuntime, pickDirectory, pickFiles } from "../../lib/tauri";
import { Button, Checkbox, ConfigModal, Input, RangeSettingField, Select } from "../ui";

type ChatConfigPanelProps = {
  config: AppConfig;
  isUpdating: boolean;
  error: string;
  folderPermissions: ChatFolderPermission[];
  isUpdatingFolderPermissions: boolean;
  folderPermissionsError: string;
  chatModelProviders: ChatModelProviderItem[];
  chatModelsError: string;
  dataEnvironment: DataEnvironmentStatus | null;
  isUpdatingDataEnvironment: boolean;
  isCreatingDataBackup: boolean;
  isImportingDataBackup: boolean;
  dataEnvironmentError: string;
  dataOperationMessage: string;
  onAddOrUpdateFolderPermission: (path: string, accessLevel: FolderAccessLevel) => Promise<void>;
  onRemoveFolderPermission: (path: string) => Promise<void>;
  onToggleTestingMode: (testingMode: boolean) => Promise<void>;
  onCreateDataBackup: (backupPath?: string) => Promise<void>;
  onImportDataBackup: (backupPath: string) => Promise<void>;
  onUpdate: (config: Partial<AppConfig>) => Promise<void>;
  onClose: () => void;
};

const CONTEXT_LIMIT_PRESETS = [
  { label: "紧凑 (3)", value: 3 },
  { label: "平衡 (6)", value: 6 },
  { label: "延续 (10)", value: 10 },
];

const READ_TIMEOUT_PRESETS = [
  { label: "1 分钟", value: 60 },
  { label: "3 分钟 (默认)", value: 180 },
  { label: "5 分钟", value: 300 },
];

export function ChatConfigPanel({
  config,
  isUpdating,
  error,
  folderPermissions,
  isUpdatingFolderPermissions,
  folderPermissionsError,
  chatModelProviders,
  chatModelsError,
  dataEnvironment,
  isUpdatingDataEnvironment,
  isCreatingDataBackup,
  isImportingDataBackup,
  dataEnvironmentError,
  dataOperationMessage,
  onAddOrUpdateFolderPermission,
  onRemoveFolderPermission,
  onToggleTestingMode,
  onCreateDataBackup,
  onImportDataBackup,
  onUpdate,
  onClose,
}: ChatConfigPanelProps) {
  const [providerDraft, setProviderDraft] = useState(config.chat_provider);
  const [modelDraft, setModelDraft] = useState(config.chat_model);
  const [modelError, setModelError] = useState("");
  const [backupPathDraft, setBackupPathDraft] = useState("");
  const [pathPickerError, setPathPickerError] = useState("");
  const hasFetchedProviders = chatModelProviders.length > 0;
  const selectedProvider = chatModelProviders.find((provider) => provider.provider_id === providerDraft);
  const modelOptions = selectedProvider?.models ?? [];
  const dataActionRunning = isUpdatingDataEnvironment || isCreatingDataBackup || isImportingDataBackup;
  const testingModeEnabled = dataEnvironment?.testing_mode ?? false;
  const canUseNativePickers = isTauriRuntime();
  const mcpEnabled = Boolean(config.chat_mcp_enabled);
  const mcpServers = Array.isArray(config.chat_mcp_servers) ? config.chat_mcp_servers : [];

  useEffect(() => {
    setProviderDraft(config.chat_provider);
    setModelDraft(config.chat_model);
  }, [config.chat_model, config.chat_provider]);

  useEffect(() => {
    if (!selectedProvider) {
      return;
    }
    if (modelOptions.includes(modelDraft)) {
      return;
    }
    if (selectedProvider.default_model) {
      setModelDraft(selectedProvider.default_model);
      return;
    }
    if (modelOptions.length > 0) {
      setModelDraft(modelOptions[0]);
    }
  }, [modelDraft, modelOptions, selectedProvider]);

  useEffect(() => {
    if (!dataEnvironment?.default_backup_directory) {
      return;
    }
    if (backupPathDraft.trim()) {
      return;
    }
    setBackupPathDraft(dataEnvironment.default_backup_directory);
  }, [backupPathDraft, dataEnvironment?.default_backup_directory]);

  return (
    <ConfigModal
      title="配置"
      onClose={onClose}
      error={error}
    >
      <div className="config-panel__row">
        <RangeSettingField
          label="聊天记忆预算"
          description="控制近期对话与长期记忆检索的预算，不限制 persona、system、附件或技能说明等其他提示层。"
          min={1}
          max={20}
          value={config.chat_context_limit}
          presets={CONTEXT_LIMIT_PRESETS}
          disabled={isUpdating}
          onChange={(value) => {
            void onUpdate({ chat_context_limit: value });
          }}
        />

        <RangeSettingField
          label="上游读取超时 (秒)"
          description="控制与上游聊天模型通信时的读取超时；主要影响流式输出和工具链路等待，不是前端页面等待时间。"
          min={10}
          max={600}
          value={config.chat_read_timeout_seconds}
          presets={READ_TIMEOUT_PRESETS}
          disabled={isUpdating}
          onChange={(value) => {
            void onUpdate({ chat_read_timeout_seconds: value });
          }}
        />
      </div>

      <div className="config-panel__section config-panel__section--model">
        <div className="config-panel__section-header">
          <span className="config-panel__section-icon">🤖</span>
          <label className="config-panel__label">聊天模型</label>
        </div>

        <div className="config-panel__model-list">
          <div className="config-panel__model-line">
            <label className="config-panel__model-label" htmlFor="chat-config-provider-select">
              <span className="config-panel__model-icon">🏢</span>
              <span>服务商</span>
            </label>
            <Select
              id="chat-config-provider-select"
              aria-label="模型服务商"
              className="config-panel__model-select"
              value={providerDraft}
              disabled={isUpdating || !hasFetchedProviders}
              onChange={(event) => {
                const nextProvider = event.target.value;
                const provider = chatModelProviders.find((item) => item.provider_id === nextProvider);
                const nextModel = provider?.models.includes(modelDraft)
                  ? modelDraft
                  : (provider?.default_model ?? provider?.models?.[0] ?? modelDraft);

                setProviderDraft(nextProvider);
                setModelDraft(nextModel);
                if (modelError) setModelError("");
                void onUpdate({ chat_provider: nextProvider, chat_model: nextModel }).catch(() => {});
              }}
            >
              {chatModelProviders.map((provider) => (
                <option key={provider.provider_id} value={provider.provider_id}>
                  {provider.provider_name}
                </option>
              ))}
            </Select>
          </div>

          <div className="config-panel__model-line">
            <label className="config-panel__model-label" htmlFor="chat-config-model-select">
              <span className="config-panel__model-icon">💬</span>
              <span>模型</span>
            </label>
            <Select
              id="chat-config-model-select"
              aria-label="聊天模型"
              className="config-panel__model-select"
              value={modelDraft}
              disabled={isUpdating || !hasFetchedProviders || modelOptions.length === 0}
              onChange={(event) => {
                const nextModel = event.target.value;
                setModelDraft(nextModel);
                if (modelError) {
                  setModelError("");
                }
                void onUpdate({ chat_provider: providerDraft, chat_model: nextModel }).catch(() => {});
              }}
            >
              {modelOptions.map((model) => (
                <option key={model} value={model}>
                  {model}
                </option>
              ))}
            </Select>
          </div>
        </div>

        {selectedProvider?.error ? (
          <div className="config-panel__error-box">
            <span className="config-panel__error-icon">⚠</span>
            <span>{selectedProvider.error}</span>
          </div>
        ) : null}
        {chatModelsError ? (
          <div className="config-panel__error-box">
            <span className="config-panel__error-icon">⚠</span>
            <span>{chatModelsError}</span>
          </div>
        ) : null}
        {modelError ? (
          <div className="config-panel__error-box">
            <span className="config-panel__error-icon">⚠</span>
            <span>{modelError}</span>
          </div>
        ) : null}
      </div>

      <div className="config-panel__section">
        <div className="config-panel__section-header">
          <span className="config-panel__section-icon">🧠</span>
          <label className="config-panel__label" htmlFor="chat-config-continuous-reasoning">
            持续推理
          </label>
        </div>
        <p className="config-panel__description">
          开启后会为当前回复附带 reasoning session 标记，并在失败后继续生成时沿用同一会话；普通新一轮对话会优先接续最近一次推理会话。
        </p>
        <label className="config-panel__switch-row" htmlFor="chat-config-continuous-reasoning">
          <span>启用持续推理</span>
          <Checkbox
            id="chat-config-continuous-reasoning"
            aria-label="启用持续推理"
            checked={Boolean(config.chat_continuous_reasoning_enabled)}
            disabled={isUpdating}
            onChange={(event) => {
              void onUpdate({ chat_continuous_reasoning_enabled: event.target.checked });
            }}
          />
        </label>
      </div>

      <div className="config-panel__section">
        <div className="config-panel__section-header">
          <span className="config-panel__section-icon">🧩</span>
          <label className="config-panel__label">MCP 工具</label>
        </div>
        <p className="config-panel__description">
          MCP 管理入口已迁移到工具箱，此处仅展示当前状态与配置快照。
        </p>
        <div className="config-panel__mcp-hint">
          当前状态：{mcpEnabled ? "已启用" : "未启用"}。如需新增、编辑、删除或启停，请前往“工具箱 {"->"} MCP”。
        </div>
        {mcpServers.length === 0 ? (
          <div className="config-panel__mcp-hint">当前没有配置 MCP Server。</div>
        ) : (
          <div className="config-panel__mcp-list">
            {mcpServers.map((server) => (
              <div key={server.server_id} className="config-panel__mcp-item">
                <div className="config-panel__mcp-item-main">
                  <strong>{server.server_id}</strong>
                  <span>
                    {server.command} {server.args.join(" ")}
                  </span>
                  <span className="config-panel__mcp-meta">
                    timeout: {server.timeout_seconds}s
                    {server.cwd ? ` · cwd: ${server.cwd}` : ""}
                  </span>
                </div>
                <div className="config-panel__mcp-item-actions">
                  <span className="config-panel__item-action">默认状态：{server.enabled ? "启用" : "停用"}</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="config-panel__section">
        <div className="config-panel__section-header">
          <span className="config-panel__section-icon">🧪</span>
          <label className="config-panel__label">测试隔离与备份</label>
        </div>
        <p className="config-panel__description">
          开启后会先自动备份，再切到隔离的数据环境，测试不会污染当前记忆/聊天数据。
        </p>
        <div className="config-panel__filesystem-compact">
          <div className="config-panel__fs-path">
            {dataEnvironment?.mempalace_palace_path ?? "未加载数据环境路径"}
          </div>
          <div className="config-panel__fs-footer">
            <div className={`config-panel__fs-status ${testingModeEnabled ? "config-panel__fs-status--active" : ""}`}>
              <span className="config-panel__fs-status-dot" />
              {testingModeEnabled ? "当前为测试隔离环境" : "当前为默认数据环境"}
            </div>
            <div className="config-panel__fs-actions">
              <Button
                type="button"
                variant="default"
                className="config-panel__fs-btn config-panel__fs-btn--primary"
                disabled={dataActionRunning}
                onClick={() => {
                  void onToggleTestingMode(!testingModeEnabled);
                }}
              >
                {testingModeEnabled ? "退出测试隔离" : "进入测试隔离（自动备份）"}
              </Button>
            </div>
          </div>
        </div>

        <div className="config-panel__backup-box">
          <label className="config-panel__label" htmlFor="chat-config-backup-path">
            备份目录或备份文件路径
          </label>
          <Input
            id="chat-config-backup-path"
            aria-label="备份路径"
            className="config-panel__backup-input"
            value={backupPathDraft}
            onChange={(event) => setBackupPathDraft(event.target.value)}
            placeholder={dataEnvironment?.default_backup_directory ?? "例如 /tmp/xiaoyan-backups"}
            disabled={dataActionRunning}
          />
          <div className="config-panel__backup-picker-actions">
            <Button
              type="button"
              variant="secondary"
              className="config-panel__fs-btn"
              disabled={dataActionRunning || !canUseNativePickers}
              onClick={() => {
                void (async () => {
                  setPathPickerError("");
                  try {
                    const selected = await pickDirectory();
                    if (selected) {
                      setBackupPathDraft(selected);
                    }
                  } catch (error) {
                    setPathPickerError(error instanceof Error ? error.message : "选择目录失败");
                  }
                })();
              }}
            >
              选目录（备份）
            </Button>
            <Button
              type="button"
              variant="secondary"
              className="config-panel__fs-btn"
              disabled={dataActionRunning || !canUseNativePickers}
              onClick={() => {
                void (async () => {
                  setPathPickerError("");
                  try {
                    const selected = await pickFiles({
                      title: "选择要导入的备份文件",
                      filters: [{ name: "Backup", extensions: ["zip"] }],
                      multiple: false,
                    });
                    if (selected[0]) {
                      setBackupPathDraft(selected[0]);
                    }
                  } catch (error) {
                    setPathPickerError(error instanceof Error ? error.message : "选择备份文件失败");
                  }
                })();
              }}
            >
              选 zip（导入）
            </Button>
          </div>
          {!canUseNativePickers ? (
            <div className="config-panel__backup-hint">当前不是 Tauri 宿主，请手动输入路径。</div>
          ) : null}
          <div className="config-panel__backup-actions">
            <Button
              type="button"
              variant="secondary"
              className="config-panel__fs-btn"
              disabled={dataActionRunning}
              onClick={() => {
                void onCreateDataBackup(backupPathDraft);
              }}
            >
              {isCreatingDataBackup ? "备份中..." : "立即备份"}
            </Button>
            <Button
              type="button"
              variant="destructive"
              className="config-panel__fs-btn config-panel__fs-btn--danger"
              disabled={dataActionRunning}
              onClick={() => {
                void onImportDataBackup(backupPathDraft);
              }}
            >
              {isImportingDataBackup ? "导入中..." : "导入备份（先自动备份）"}
            </Button>
          </div>
        </div>

        {dataOperationMessage ? (
          <div className="config-panel__success-box">
            <span className="config-panel__success-icon">✓</span>
            <span>{dataOperationMessage}</span>
          </div>
        ) : null}
        {dataEnvironmentError ? (
          <div className="config-panel__error-box">
            <span className="config-panel__error-icon">⚠</span>
            <span>{dataEnvironmentError}</span>
          </div>
        ) : null}
        {pathPickerError ? (
          <div className="config-panel__error-box">
            <span className="config-panel__error-icon">⚠</span>
            <span>{pathPickerError}</span>
          </div>
        ) : null}
      </div>
    </ConfigModal>
  );
}
