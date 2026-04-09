import { useEffect, useMemo, useState } from "react";
import type {
  AppConfig,
  ChatFolderPermission,
  ChatModelProviderItem,
  FolderAccessLevel,
} from "../../lib/api";
import {
  addImportedProject,
  applyFolderPermissionsToRegistry,
  buildFolderPermissionPlan,
  loadImportedProjectRegistry,
  normalizeProjectPath,
  removeImportedProject,
  saveImportedProjectRegistry,
  setActiveImportedProject,
  type ImportedProjectRegistry,
} from "../../lib/projects";
import {
  fsClearAllowedDirectory,
  fsGetAllowedDirectory,
  fsSetAllowedDirectory,
  isTauriRuntime,
  pickDirectory,
} from "../../lib/tauri";
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
  const [tauriAllowedDir, setTauriAllowedDir] = useState<string | null>(null);
  const [tauriFsError, setTauriFsError] = useState("");
  const [projectRegistry, setProjectRegistry] = useState<ImportedProjectRegistry>(() =>
    loadImportedProjectRegistry(),
  );
  const [projectError, setProjectError] = useState("");
  const [isUpdatingProjects, setIsUpdatingProjects] = useState(false);
  const hasFetchedProviders = chatModelProviders.length > 0;
  const selectedProvider = chatModelProviders.find((provider) => provider.provider_id === providerDraft);
  const modelOptions = selectedProvider?.models ?? [];
  const projectPermissionPlan = useMemo(
    () => buildFolderPermissionPlan(projectRegistry),
    [projectRegistry],
  );
  const permissionByPath = useMemo(() => {
    const map = new Map<string, FolderAccessLevel>();
    for (const permission of folderPermissions) {
      map.set(normalizeProjectPath(permission.path), permission.access_level);
    }
    return map;
  }, [folderPermissions]);
  const isMutatingProjects = isUpdatingProjects || isUpdatingFolderPermissions;

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
    setProjectRegistry((previous) => {
      const next = applyFolderPermissionsToRegistry(previous, folderPermissions, tauriAllowedDir);
      if (isSameRegistry(previous, next)) {
        return previous;
      }
      saveImportedProjectRegistry(next);
      return next;
    });
  }, [folderPermissions, tauriAllowedDir]);

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

  async function syncProjectPermissionPlan(nextRegistry: ImportedProjectRegistry, removedPaths: string[] = []) {
    const plan = buildFolderPermissionPlan(nextRegistry);
    for (const permission of plan) {
      await onAddOrUpdateFolderPermission(permission.path, permission.access_level);
    }
    for (const removedPath of removedPaths) {
      await onRemoveFolderPermission(removedPath);
    }
  }

  function updateProjectRegistry(nextRegistry: ImportedProjectRegistry) {
    setProjectRegistry(nextRegistry);
    saveImportedProjectRegistry(nextRegistry);
  }

  async function handleImportProject() {
    if (!isTauriRuntime()) return;
    setTauriFsError("");
    setProjectError("");
    setIsUpdatingProjects(true);
    try {
      const selected = await pickDirectory();
      if (!selected) return;

      const nextRegistry = addImportedProject(projectRegistry, selected);
      const normalized = await fsSetAllowedDirectory(selected);
      await syncProjectPermissionPlan(nextRegistry);
      updateProjectRegistry(nextRegistry);
      setTauriAllowedDir(normalized);
    } catch (e) {
      const message = e instanceof Error ? e.message : String(e);
      setProjectError(message || "导入项目失败");
      console.error("import project failed:", e);
    } finally {
      setIsUpdatingProjects(false);
    }
  }

  async function handleActivateProject(path: string) {
    if (!isTauriRuntime()) return;
    setProjectError("");
    setIsUpdatingProjects(true);
    try {
      const normalizedPath = normalizeProjectPath(path);
      const nextRegistry = setActiveImportedProject(projectRegistry, normalizedPath);
      if (isSameRegistry(projectRegistry, nextRegistry)) {
        return;
      }

      await fsSetAllowedDirectory(normalizedPath);
      await syncProjectPermissionPlan(nextRegistry);
      updateProjectRegistry(nextRegistry);
      setTauriAllowedDir(normalizedPath);
    } catch (e) {
      const message = e instanceof Error ? e.message : String(e);
      setProjectError(message || "切换主控项目失败");
      console.error("activate project failed:", e);
    } finally {
      setIsUpdatingProjects(false);
    }
  }

  async function handleRemoveProject(path: string) {
    if (!isTauriRuntime()) return;
    setProjectError("");
    setIsUpdatingProjects(true);
    try {
      const normalizedPath = normalizeProjectPath(path);
      const activePath = projectRegistry.active_project_path
        ? normalizeProjectPath(projectRegistry.active_project_path)
        : null;
      const nextRegistry = removeImportedProject(projectRegistry, normalizedPath);
      if (isSameRegistry(projectRegistry, nextRegistry)) {
        return;
      }

      if (activePath === normalizedPath) {
        if (nextRegistry.active_project_path) {
          await fsSetAllowedDirectory(nextRegistry.active_project_path);
          setTauriAllowedDir(nextRegistry.active_project_path);
        } else {
          await fsClearAllowedDirectory();
          setTauriAllowedDir(null);
        }
      }

      const shouldRemovePermission = permissionByPath.has(normalizedPath);
      await syncProjectPermissionPlan(nextRegistry, shouldRemovePermission ? [normalizedPath] : []);
      updateProjectRegistry(nextRegistry);
    } catch (e) {
      const message = e instanceof Error ? e.message : String(e);
      setProjectError(message || "移除项目失败");
      console.error("remove project failed:", e);
    } finally {
      setIsUpdatingProjects(false);
    }
  }

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

      {isTauriRuntime() ? (
        <div className="config-panel__section config-panel__section--filesystem">
          <div className="config-panel__section-header">
            <span className="config-panel__section-icon">💾</span>
            <label className="config-panel__label">项目主控</label>
          </div>

          <div className="config-panel__filesystem-compact">
            <div className="config-panel__project-header">
              <div className={`config-panel__fs-status ${tauriAllowedDir ? "config-panel__fs-status--active" : ""}`}>
                <span className="config-panel__fs-status-dot"></span>
                <span className="config-panel__fs-status-text">
                  {tauriAllowedDir ? "已设置主控项目" : "未设置主控项目"}
                </span>
              </div>
              <button
                type="button"
                className="config-panel__fs-btn config-panel__fs-btn--primary"
                onClick={() => void handleImportProject()}
                disabled={isMutatingProjects}
              >
                导入项目
              </button>
            </div>

            {projectRegistry.projects.length === 0 ? (
              <div className="config-panel__project-empty">还没有导入项目，先选择一个项目文件夹。</div>
            ) : (
              <ul className="config-panel__project-list">
                {projectRegistry.projects.map((project) => {
                  const normalizedPath = normalizeProjectPath(project.path);
                  const isActive = normalizedPath === normalizeProjectPath(projectRegistry.active_project_path ?? "");
                  const permission = permissionByPath.get(normalizedPath);

                  return (
                    <li key={normalizedPath} className={`config-panel__project-item ${isActive ? "is-active" : ""}`}>
                      <div className="config-panel__project-main">
                        <div className="config-panel__project-name-row">
                          <strong className="config-panel__project-name">{project.name}</strong>
                          <span className={`config-panel__project-badge ${isActive ? "is-active" : ""}`}>
                            {isActive ? "主控" : "已导入"}
                          </span>
                          {permission ? (
                            <span className="config-panel__project-badge config-panel__project-badge--muted">
                              {permission === "full_access" ? "可读写" : "只读"}
                            </span>
                          ) : null}
                        </div>
                        <div className="config-panel__project-path" title={normalizedPath}>
                          {normalizedPath}
                        </div>
                      </div>
                      <div className="config-panel__project-actions">
                        <button
                          type="button"
                          className="config-panel__fs-btn"
                          onClick={() => void handleActivateProject(normalizedPath)}
                          disabled={isMutatingProjects || isActive}
                        >
                          设为主控
                        </button>
                        <button
                          type="button"
                          className="config-panel__fs-btn config-panel__fs-btn--danger"
                          onClick={() => void handleRemoveProject(normalizedPath)}
                          disabled={isMutatingProjects}
                        >
                          移除
                        </button>
                      </div>
                    </li>
                  );
                })}
              </ul>
            )}

            <div className="config-panel__fs-footer">
              <div className="config-panel__fs-status">
                <span className="config-panel__fs-status-text">
                  共导入 {projectRegistry.projects.length} 个项目，当前主控:
                  {" "}
                  {projectRegistry.active_project_path ? normalizeProjectPath(projectRegistry.active_project_path) : "无"}
                </span>
              </div>
            </div>
          </div>

          {tauriFsError ? (
            <div className="config-panel__error-box">
              <span className="config-panel__error-icon">⚠</span>
              <span>{tauriFsError}</span>
            </div>
          ) : null}
          {projectError ? (
            <div className="config-panel__error-box">
              <span className="config-panel__error-icon">⚠</span>
              <span>{projectError}</span>
            </div>
          ) : null}
          {folderPermissionsError ? (
            <div className="config-panel__error-box">
              <span className="config-panel__error-icon">⚠</span>
              <span>{folderPermissionsError}</span>
            </div>
          ) : null}
          {projectPermissionPlan.length > 0 ? (
            <div className="config-panel__description">
              权限策略：主控项目可读写，其他导入项目默认只读。
            </div>
          ) : null}
        </div>
      ) : null}

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

function isSameRegistry(a: ImportedProjectRegistry, b: ImportedProjectRegistry): boolean {
  if (normalizeProjectPath(a.active_project_path ?? "") !== normalizeProjectPath(b.active_project_path ?? "")) {
    return false;
  }
  if (a.projects.length !== b.projects.length) {
    return false;
  }

  for (let index = 0; index < a.projects.length; index += 1) {
    const left = a.projects[index];
    const right = b.projects[index];
    if (
      normalizeProjectPath(left?.path ?? "") !== normalizeProjectPath(right?.path ?? "") ||
      (left?.name ?? "") !== (right?.name ?? "") ||
      (left?.imported_at ?? "") !== (right?.imported_at ?? "")
    ) {
      return false;
    }
  }

  return true;
}
