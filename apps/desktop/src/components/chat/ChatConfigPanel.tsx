import { useEffect, useRef, useState } from "react";
import type { ChangeEvent } from "react";
import type { AppConfig, ChatFolderPermission, ChatModelProviderItem, FolderAccessLevel } from "../../lib/api";
import { fsClearAllowedDirectory, fsGetAllowedDirectory, fsSetAllowedDirectory, isTauriRuntime, pickDirectory } from "../../lib/tauri";
import { ConfigModal, RangeSettingField } from "../ui";

type ChatConfigPanelProps = {
  config: AppConfig;
  isUpdating: boolean;
  error: string;
  chatModelProviders: ChatModelProviderItem[];
  chatModelsError: string;
  folderPermissions: ChatFolderPermission[];
  isUpdatingFolderPermissions: boolean;
  folderPermissionsError: string;
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

const FOLDER_PATH_PRESETS = [
  { label: "桌面", path: "~/Desktop" },
  { label: "文档", path: "~/Documents" },
  { label: "下载", path: "~/Downloads" },
];

export function ChatConfigPanel({
  config,
  isUpdating,
  error,
  chatModelProviders,
  chatModelsError,
  folderPermissions,
  isUpdatingFolderPermissions,
  folderPermissionsError,
  onAddOrUpdateFolderPermission,
  onRemoveFolderPermission,
  onUpdate,
  onClose,
}: ChatConfigPanelProps) {
  const pickerInputRef = useRef<HTMLInputElement>(null);
  const [selectedFolderPath, setSelectedFolderPath] = useState("");
  const [accessLevel, setAccessLevel] = useState<FolderAccessLevel>("read_only");
  const [pickerError, setPickerError] = useState("");
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
    const input = pickerInputRef.current;
    if (!input) {
      return;
    }
    input.setAttribute("webkitdirectory", "");
    input.setAttribute("directory", "");
  }, []);

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

  function handleSystemFolderPick() {
    setPickerError("");
    pickerInputRef.current?.click();
  }

  function handlePickerChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0] ?? null;
    const folderPath = extractFolderPathFromPickedFile(file);
    if (!folderPath) {
      setPickerError("无法从系统选择器获取路径（浏览器安全限制），请手动输入文件夹绝对路径");
      return;
    }
    setSelectedFolderPath(folderPath);
    setPickerError("");
  }

  async function handleAddOrUpdateClick() {
    const normalizedPath = selectedFolderPath.trim();
    if (!normalizedPath) {
      setPickerError("请先选择文件夹，或手动输入绝对路径");
      return;
    }
    if (!isLikelyAbsolutePath(normalizedPath)) {
      setPickerError("请输入绝对路径，例如 /Users/name/workspace 或 C:\\workspace");
      return;
    }
    
    // 检查是否已存在
    const existingPermission = folderPermissions.find(p => p.path === normalizedPath);
    if (existingPermission) {
      if (existingPermission.access_level === accessLevel) {
        setPickerError(`文件夹 "${normalizedPath}" 已存在且权限相同`);
        return;
      }
    }
    
    await onAddOrUpdateFolderPermission(normalizedPath, accessLevel);
    setSelectedFolderPath("");
    setAccessLevel("read_only");
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

      <div className="config-panel__section">
        <label className="config-panel__label">文件夹访问权限</label>
        <p className="config-panel__description">
          授权聊天可访问的文件夹目录。可通过系统选择器或手动输入绝对路径。
          <br />
          <span className="config-panel__hint">
            提示：系统选择器在某些浏览器可能无法获取路径，如遇此情况请手动输入路径
          </span>
        </p>

        <input
          ref={pickerInputRef}
          aria-label="系统文件夹选择器"
          type="file"
          className="chat-config-file-input"
          onChange={handlePickerChange}
          onClick={(event) => {
            (event.currentTarget as HTMLInputElement).value = "";
          }}
        />

        <div className="config-panel__folder-picker-row">
          <div className="config-panel__folder-picker-main">
            <button
              type="button"
              className="config-panel__preset config-panel__folder-picker-btn"
              onClick={handleSystemFolderPick}
              disabled={isUpdatingFolderPermissions}
            >
              选择文件夹
            </button>
            <label className="sr-only" htmlFor="chat-config-folder-path">
              文件夹绝对路径
            </label>
            <input
              id="chat-config-folder-path"
              className="config-panel__folder-input"
              placeholder="/Users/name/workspace"
              value={selectedFolderPath}
              onChange={(event) => {
                setSelectedFolderPath(event.target.value);
                if (pickerError) {
                  setPickerError("");
                }
              }}
              disabled={isUpdatingFolderPermissions}
            />
            <label className="sr-only" htmlFor="chat-config-folder-access">
              权限级别
            </label>
            <select
              id="chat-config-folder-access"
              className="config-panel__folder-select"
              value={accessLevel}
              onChange={(event) => setAccessLevel(event.target.value as FolderAccessLevel)}
              disabled={isUpdatingFolderPermissions}
              aria-label="权限级别"
            >
              <option value="read_only">只读</option>
              <option value="full_access">完全访问</option>
            </select>
          </div>
          <button
            type="button"
            className="config-panel__btn config-panel__btn--primary config-panel__folder-add-btn"
            onClick={() => void handleAddOrUpdateClick()}
            disabled={isUpdatingFolderPermissions}
          >
            添加/更新权限
          </button>
        </div>

        {pickerError ? <p className="config-panel__folder-error">{pickerError}</p> : null}
        {folderPermissionsError ? <p className="config-panel__folder-error">{folderPermissionsError}</p> : null}

        <div className="config-panel__folder-presets">
          <span className="config-panel__folder-presets-label">快捷路径：</span>
          {FOLDER_PATH_PRESETS.map((preset) => (
            <button
              key={preset.path}
              type="button"
              className="config-panel__folder-preset-btn"
              onClick={() => {
                setSelectedFolderPath(preset.path);
                setPickerError("");
              }}
              disabled={isUpdatingFolderPermissions}
            >
              {preset.label}
            </button>
          ))}
        </div>

        {folderPermissions.length === 0 ? (
          <p className="config-panel__folder-empty">当前未授权任何文件夹</p>
        ) : (
          <ul className="config-panel__folder-list">
            {folderPermissions.map((permission) => (
              <li key={permission.path} className="config-panel__folder-item">
                <code className="config-panel__folder-item-path">{permission.path}</code>
                <span 
                  className="config-panel__folder-badge"
                  data-level={permission.access_level}
                >
                  {permission.access_level === "full_access" ? "可读写" : "只读"}
                </span>
                <button
                  type="button"
                  className="config-panel__btn config-panel__btn--danger"
                  onClick={() => void onRemoveFolderPermission(permission.path)}
                  disabled={isUpdatingFolderPermissions}
                  title="移除此文件夹权限"
                >
                  移除
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </ConfigModal>
  );
}

function isLikelyAbsolutePath(path: string): boolean {
  if (path.startsWith("/")) {
    return true;
  }
  if (path.startsWith("~/")) {
    return true;
  }
  return /^[A-Za-z]:[\\/]/.test(path);
}

function extractFolderPathFromPickedFile(file: File | null): string | null {
  if (!file) {
    return null;
  }

  const pickedFile = file as File & { path?: string; webkitRelativePath?: string };
  const absoluteFilePath = pickedFile.path;
  if (!absoluteFilePath) {
    return null;
  }

  const relativePath = pickedFile.webkitRelativePath || file.webkitRelativePath || file.name;
  if (!relativePath) {
    return null;
  }

  const normalizedAbsolute = absoluteFilePath.replace(/\\/g, "/");
  const normalizedRelative = relativePath.replace(/\\/g, "/");
  const absoluteFileDir = normalizedAbsolute.slice(0, normalizedAbsolute.lastIndexOf("/"));
  const relativeDir = normalizedRelative.includes("/") ? normalizedRelative.slice(0, normalizedRelative.lastIndexOf("/")) : "";

  if (!relativeDir) {
    return absoluteFileDir || "/";
  }

  const relativeParts = relativeDir.split("/").filter(Boolean);
  const subPathUnderRoot = relativeParts.slice(1).join("/");
  if (!subPathUnderRoot) {
    return absoluteFileDir || "/";
  }

  if (absoluteFileDir.endsWith(`/${subPathUnderRoot}`)) {
    const rootFolderPath = absoluteFileDir.slice(0, absoluteFileDir.length - subPathUnderRoot.length - 1);
    return rootFolderPath || "/";
  }

  return absoluteFileDir || "/";
}
