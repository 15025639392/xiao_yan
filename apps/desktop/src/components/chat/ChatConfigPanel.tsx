import { useEffect, useState } from "react";
import type {
  AppConfig,
  ChatFolderPermission,
  ChatModelProviderItem,
  FolderAccessLevel,
} from "../../lib/api";
import { ConfigModal, RangeSettingField } from "../ui";

type ChatConfigPanelProps = {
  config: AppConfig;
  isUpdating: boolean;
  error: string;
  folderPermissions: ChatFolderPermission[];
  isUpdatingFolderPermissions: boolean;
  folderPermissionsError: string;
  chatModelProviders: ChatModelProviderItem[];
  chatModelsError: string;
  onAddOrUpdateFolderPermission: (path: string, accessLevel: FolderAccessLevel) => Promise<void>;
  onRemoveFolderPermission: (path: string) => Promise<void>;
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
  folderPermissions,
  isUpdatingFolderPermissions,
  folderPermissionsError,
  chatModelProviders,
  chatModelsError,
  onAddOrUpdateFolderPermission,
  onRemoveFolderPermission,
  onUpdate,
  onClose,
}: ChatConfigPanelProps) {
  const [providerDraft, setProviderDraft] = useState(config.chat_provider);
  const [modelDraft, setModelDraft] = useState(config.chat_model);
  const [modelError, setModelError] = useState("");
  const hasFetchedProviders = chatModelProviders.length > 0;
  const selectedProvider = chatModelProviders.find((provider) => provider.provider_id === providerDraft);
  const modelOptions = selectedProvider?.models ?? [];

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

  return (
    <ConfigModal
      title="配置"
      onClose={onClose}
      error={error}
    >
      <div className="config-panel__row">
        <RangeSettingField
          label="聊天上下文限制"
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
            <select
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
            </select>
          </div>

          <div className="config-panel__model-line">
            <label className="config-panel__model-label" htmlFor="chat-config-model-select">
              <span className="config-panel__model-icon">💬</span>
              <span>模型</span>
            </label>
            <select
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
            </select>
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
    </ConfigModal>
  );
}
