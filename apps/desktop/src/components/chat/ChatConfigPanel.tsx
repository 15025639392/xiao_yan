import { useEffect, useState } from "react";
import type { AppConfig, ChatModelProviderItem } from "../../lib/api";
import { fsClearAllowedDirectory, fsGetAllowedDirectory, fsSetAllowedDirectory, isTauriRuntime, pickDirectory } from "../../lib/tauri";
import { ConfigModal, RangeSettingField } from "../ui";

type ChatConfigPanelProps = {
  config: AppConfig;
  isUpdating: boolean;
  error: string;
  chatModelProviders: ChatModelProviderItem[];
  chatModelsError: string;
  onUpdate: (config: Partial<AppConfig>) => Promise<void>;
  onClose: () => void;
};

const CONTEXT_LIMIT_PRESETS = [
  { label: "保守 (3)", value: 3 },
  { label: "默认 (6)", value: 6 },
  { label: "开放 (10)", value: 10 },
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
  chatModelProviders,
  chatModelsError,
  onUpdate,
  onClose,
}: ChatConfigPanelProps) {
  const [providerDraft, setProviderDraft] = useState(config.chat_provider);
  const [modelDraft, setModelDraft] = useState(config.chat_model);
  const [modelError, setModelError] = useState("");
  const [tauriAllowedDir, setTauriAllowedDir] = useState<string | null>(null);
  const [tauriFsError, setTauriFsError] = useState("");
  const [isUpdatingTauriFs, setIsUpdatingTauriFs] = useState(false);
  const hasFetchedProviders = chatModelProviders.length > 0;
  const selectedProvider = chatModelProviders.find((provider) => provider.provider_id === providerDraft);
  const modelOptions = selectedProvider?.models ?? [];

  useEffect(() => {
    setProviderDraft(config.chat_provider);
    setModelDraft(config.chat_model);
  }, [config.chat_model, config.chat_provider]);

  useEffect(() => {
    if (!isTauriRuntime()) return;
    fsGetAllowedDirectory()
      .then(setTauriAllowedDir)
      .catch((e) => setTauriFsError(e instanceof Error ? e.message : "读取本地权限失败"));
  }, []);

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

  async function handleApplyModel() {
    const nextProvider = providerDraft.trim();
    if (!nextProvider) {
      setModelError("服务商不能为空");
      return;
    }
    const provider = chatModelProviders.find((item) => item.provider_id === nextProvider);
    if (!provider) {
      setModelError("请选择有效的服务商");
      return;
    }

    const nextModel = modelDraft.trim() || provider.default_model.trim();
    if (!nextModel.trim()) {
      setModelError("模型名不能为空");
      return;
    }
    try {
      setModelError("");
      await onUpdate({ chat_provider: nextProvider, chat_model: nextModel });
    } catch {
      // 错误由父级统一处理并展示在 ConfigModal 顶部
    }
  }

  async function handlePickTauriAllowedDir() {
    if (!isTauriRuntime()) return;
    setTauriFsError("");
    setIsUpdatingTauriFs(true);
    try {
      const selected = await pickDirectory();
      if (!selected) return;
      const normalized = await fsSetAllowedDirectory(selected);
      setTauriAllowedDir(normalized);
    } catch (e) {
      const message = e instanceof Error ? e.message : String(e);
      setTauriFsError(message || "设置本地权限失败");
      console.error("set allowed dir failed:", e);
    } finally {
      setIsUpdatingTauriFs(false);
    }
  }

  async function handleClearTauriAllowedDir() {
    if (!isTauriRuntime()) return;
    setTauriFsError("");
    setIsUpdatingTauriFs(true);
    try {
      await fsClearAllowedDirectory();
      setTauriAllowedDir(null);
    } catch (e) {
      const message = e instanceof Error ? e.message : String(e);
      setTauriFsError(message || "清除本地权限失败");
      console.error("clear allowed dir failed:", e);
    } finally {
      setIsUpdatingTauriFs(false);
    }
  }

  return (
    <ConfigModal
      title="配置"
      onClose={onClose}
      error={error}
      actions={[{ key: "done", label: "完成", tone: "primary", onClick: onClose }]}
    >
      <RangeSettingField
        label="聊天上下文限制"
        description="每次聊天时携带的相关事件数量。值越小响应越快，但连贯性可能降低；值越大对话越连贯，但响应可能变慢。"
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
        label="Read 超时 (秒)"
        description="用于流式输出：只要持续有输出，计时会自动刷新；只有长时间无任何输出才会超时。"
        min={10}
        max={600}
        value={config.chat_read_timeout_seconds}
        presets={READ_TIMEOUT_PRESETS}
        disabled={isUpdating}
        onChange={(value) => {
          void onUpdate({ chat_read_timeout_seconds: value });
        }}
      />

      {isTauriRuntime() ? (
        <div className="config-panel__section">
          <label className="config-panel__label">本地文件系统 (Tauri)</label>
          <p className="config-panel__description">
            选择一个允许访问的根目录。Tauri 侧只允许读取/写入该目录内的相对路径，禁止绝对路径与 .. 越权。
          </p>

          <div className="config-panel__folder-picker-row">
            <div className="config-panel__folder-picker-main" style={{ gap: "var(--space-2)" }}>
              <button
                type="button"
                className="config-panel__btn config-panel__btn--primary"
                onClick={() => void handlePickTauriAllowedDir()}
                disabled={isUpdatingTauriFs}
              >
                选择允许目录
              </button>
              <button
                type="button"
                className="config-panel__btn config-panel__btn--danger"
                onClick={() => void handleClearTauriAllowedDir()}
                disabled={isUpdatingTauriFs || !tauriAllowedDir}
                title="清除本地目录授权"
              >
                清除
              </button>
              <span style={{ fontSize: "0.875rem", color: "var(--text-secondary)" }}>
                {tauriAllowedDir ? `已授权: ${tauriAllowedDir}` : "未授权"}
              </span>
            </div>
          </div>

          {tauriFsError ? <p className="config-panel__folder-error">{tauriFsError}</p> : null}
        </div>
      ) : null}

      <div className="config-panel__section">
        <label className="config-panel__label">聊天模型</label>
        <p className="config-panel__description">
          模型列表按服务商从后端实时获取。修改后新发起的聊天会使用所选服务商与模型。
        </p>
        <div className="config-panel__model-row">
          <select
            id="chat-config-provider-select"
            aria-label="模型服务商"
            className="config-panel__folder-select"
            value={providerDraft}
            disabled={isUpdating || !hasFetchedProviders}
            onChange={(event) => {
              const nextProvider = event.target.value;
              setProviderDraft(nextProvider);
              const provider = chatModelProviders.find((item) => item.provider_id === nextProvider);
              if (provider) {
                if (provider.models.includes(modelDraft)) {
                  return;
                }
                if (provider.default_model) {
                  setModelDraft(provider.default_model);
                  return;
                }
                if (provider.models.length > 0) {
                  setModelDraft(provider.models[0]);
                }
              }
            }}
          >
            {chatModelProviders.map((provider) => (
              <option key={provider.provider_id} value={provider.provider_id}>
                {provider.provider_name}
              </option>
            ))}
          </select>
        </div>
        <div className="config-panel__model-row">
          <select
            id="chat-config-model-select"
            aria-label="聊天模型"
            className="config-panel__folder-select"
            value={modelDraft}
            disabled={isUpdating || !hasFetchedProviders || modelOptions.length === 0}
            onChange={(event) => {
              setModelDraft(event.target.value);
              if (modelError) {
                setModelError("");
              }
            }}
          >
            {modelOptions.map((model) => (
              <option key={model} value={model}>
                {model}
              </option>
            ))}
          </select>
          <button
            type="button"
            className="config-panel__btn config-panel__btn--primary"
            disabled={isUpdating || !hasFetchedProviders}
            onClick={() => void handleApplyModel()}
          >
            应用模型
          </button>
        </div>
        {selectedProvider?.error ? <p className="config-panel__folder-error">{selectedProvider.error}</p> : null}
        {chatModelsError ? <p className="config-panel__folder-error">{chatModelsError}</p> : null}
        {modelError ? <p className="config-panel__folder-error">{modelError}</p> : null}
      </div>
    </ConfigModal>
  );
}
