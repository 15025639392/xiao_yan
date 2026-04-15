import { useCallback, useEffect, useRef, useState } from "react";
import type { KeyboardEvent as ReactKeyboardEvent, RefObject } from "react";
import type {
  AppConfig,
  ChatFolderPermission,
  ChatModelProviderItem,
  DataEnvironmentStatus,
  FolderAccessLevel,
  RelationshipSummary,
} from "../../lib/api";
import {
  createDataBackup,
  DEFAULT_CHAT_PROVIDER,
  DEFAULT_CHAT_MODEL,
  fetchChatModels,
  fetchChatFolderPermissions,
  fetchConfig,
  fetchDataEnvironmentStatus,
  fetchMemorySummary,
  importDataBackup,
  removeChatFolderPermission,
  updateDataEnvironmentStatus,
  updateConfig,
  upsertChatFolderPermission,
} from "../../lib/api";
import { subscribeAppRealtime } from "../../lib/realtime";
import type { ChatEntry, ChatSendOptions } from "./chatTypes";
import { useChatScrollBehavior } from "./useChatScrollBehavior";

function listEnabledMcpServerIds(config: AppConfig): string[] {
  return (Array.isArray(config.chat_mcp_servers) ? config.chat_mcp_servers : [])
    .filter((server) => server.enabled)
    .map((server) => server.server_id);
}

type UseChatPanelStateArgs = {
  draft: string;
  messages: ChatEntry[];
  isSending: boolean;
  onSend: (options?: ChatSendOptions) => void;
};

type UseChatPanelStateResult = {
  textareaRef: RefObject<HTMLTextAreaElement>;
  messagesEndRef: RefObject<HTMLDivElement>;
  messagesContainerRef: RefObject<HTMLDivElement>;
  relationship: RelationshipSummary | null;
  showMemoryContext: Set<string>;
  showConfigPanel: boolean;
  config: AppConfig;
  isUpdatingConfig: boolean;
  configError: string;
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
  toggleMemoryContext: (messageId: string) => void;
  toggleConfigPanel: () => void;
  closeConfigPanel: () => void;
  handleAddOrUpdateFolderPermission: (path: string, accessLevel: FolderAccessLevel) => Promise<void>;
  handleRemoveFolderPermission: (path: string) => Promise<void>;
  handleToggleTestingMode: (testingMode: boolean) => Promise<void>;
  handleCreateDataBackup: (backupPath?: string) => Promise<void>;
  handleImportDataBackup: (backupPath: string) => Promise<void>;
  handleKeyDown: (event: ReactKeyboardEvent<HTMLTextAreaElement>) => void;
  handleSubmit: () => void;
  handleUpdateConfig: (newConfig: Partial<AppConfig>) => Promise<void>;
  mcpEnabled: boolean;
  availableMcpServers: AppConfig["chat_mcp_servers"];
  selectedMcpServerIds: string[] | null;
  isLoadingMcpServerSelection: boolean;
  mcpServerSelectionError: string;
  handleOpenMcpServerSelector: () => Promise<void>;
  handleToggleMcpServerSelection: (serverId: string) => void;
};

export function useChatPanelState({ draft, messages, isSending, onSend }: UseChatPanelStateArgs): UseChatPanelStateResult {
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const messagesContainerRef = useRef<HTMLDivElement>(null);

  const [relationship, setRelationship] = useState<RelationshipSummary | null>(null);
  const [showMemoryContext, setShowMemoryContext] = useState<Set<string>>(new Set());
  const [showConfigPanel, setShowConfigPanel] = useState(false);
  const [config, setConfig] = useState<AppConfig>({
    chat_context_limit: 6,
    chat_provider: DEFAULT_CHAT_PROVIDER,
    chat_model: DEFAULT_CHAT_MODEL,
    chat_read_timeout_seconds: 180,
    chat_mcp_enabled: false,
    chat_mcp_servers: [],
  });
  const [isUpdatingConfig, setIsUpdatingConfig] = useState(false);
  const [configError, setConfigError] = useState("");
  const [folderPermissions, setFolderPermissions] = useState<ChatFolderPermission[]>([]);
  const [isUpdatingFolderPermissions, setIsUpdatingFolderPermissions] = useState(false);
  const [folderPermissionsError, setFolderPermissionsError] = useState("");
  const [chatModelProviders, setChatModelProviders] = useState<ChatModelProviderItem[]>([]);
  const [chatModelsError, setChatModelsError] = useState("");
  const [dataEnvironment, setDataEnvironment] = useState<DataEnvironmentStatus | null>(null);
  const [isUpdatingDataEnvironment, setIsUpdatingDataEnvironment] = useState(false);
  const [isCreatingDataBackup, setIsCreatingDataBackup] = useState(false);
  const [isImportingDataBackup, setIsImportingDataBackup] = useState(false);
  const [dataEnvironmentError, setDataEnvironmentError] = useState("");
  const [dataOperationMessage, setDataOperationMessage] = useState("");
  const [selectedMcpServerIds, setSelectedMcpServerIds] = useState<string[] | null>(null);
  const [hasLoadedMcpServerSelection, setHasLoadedMcpServerSelection] = useState(false);
  const [isLoadingMcpServerSelection, setIsLoadingMcpServerSelection] = useState(false);
  const [mcpServerSelectionError, setMcpServerSelectionError] = useState("");

  const applyConfigForMcpSelection = useCallback((nextConfig: AppConfig) => {
    setConfig(nextConfig);
    setHasLoadedMcpServerSelection(true);
    setSelectedMcpServerIds((prev) => {
      if (prev === null) {
        return null;
      }
      const enabledServerIdSet = new Set(listEnabledMcpServerIds(nextConfig));
      return prev.filter((serverId) => enabledServerIdSet.has(serverId));
    });
  }, []);

  async function loadConfigAndFolderPermissions() {
    setConfigError("");
    setFolderPermissionsError("");
    setChatModelsError("");
    setDataEnvironmentError("");

    const [configResult, permissionsResult, modelsResult, dataEnvironmentResult] = await Promise.allSettled([
      fetchConfig(),
      fetchChatFolderPermissions(),
      fetchChatModels(),
      fetchDataEnvironmentStatus(),
    ]);

    if (configResult.status === "fulfilled") {
      setMcpServerSelectionError("");
      applyConfigForMcpSelection(configResult.value);
    } else {
      const message = configResult.reason instanceof Error ? configResult.reason.message : "加载配置失败";
      setConfigError(message);
      console.error("加载配置失败:", configResult.reason);
    }

    if (permissionsResult.status === "fulfilled") {
      setFolderPermissions(permissionsResult.value.permissions);
    } else {
      const message = permissionsResult.reason instanceof Error ? permissionsResult.reason.message : "加载文件夹权限失败";
      setFolderPermissionsError(message);
      console.error("加载文件夹权限失败:", permissionsResult.reason);
    }

    if (modelsResult.status === "fulfilled") {
      setChatModelProviders(modelsResult.value.providers);
    } else {
      const message = modelsResult.reason instanceof Error ? modelsResult.reason.message : "加载模型列表失败";
      setChatModelsError(message);
      console.error("加载模型列表失败:", modelsResult.reason);
    }

    if (dataEnvironmentResult.status === "fulfilled") {
      setDataEnvironment(dataEnvironmentResult.value);
    } else {
      const message = dataEnvironmentResult.reason instanceof Error ? dataEnvironmentResult.reason.message : "加载数据环境失败";
      setDataEnvironmentError(message);
      console.error("加载数据环境失败:", dataEnvironmentResult.reason);
    }
  }

  useEffect(() => {
    const textarea = textareaRef.current;
    if (!textarea) return;
    textarea.style.height = "auto";
    textarea.style.height = `${Math.min(textarea.scrollHeight, 200)}px`;
  }, [draft]);

  useEffect(() => {
    fetchMemorySummary()
      .then((summary) => setRelationship(summary.relationship))
      .catch(() => setRelationship(null));

    const unsubscribe = subscribeAppRealtime((event) => {
      const memoryPayload =
        event.type === "snapshot" ? event.payload.memory : event.type === "memory_updated" ? event.payload : null;
      if (!memoryPayload) {
        return;
      }

      setRelationship(memoryPayload.relationship ?? memoryPayload.summary.relationship ?? null);
    });

    return () => unsubscribe();
  }, []);

  useChatScrollBehavior({
    messages,
    isSending,
    messagesContainerRef,
    messagesEndRef,
  });

  const toggleMemoryContext = useCallback((messageId: string) => {
    setShowMemoryContext((prev) => {
      const next = new Set(prev);
      if (next.has(messageId)) {
        next.delete(messageId);
      } else {
        next.add(messageId);
      }
      return next;
    });
  }, []);

  function resolveSendOptions(): ChatSendOptions | undefined {
    if (selectedMcpServerIds === null) {
      return undefined;
    }
    const enabledServerIdSet = new Set(listEnabledMcpServerIds(config));
    const filteredServerIds = selectedMcpServerIds.filter((serverId) => enabledServerIdSet.has(serverId));
    return { mcpServerIds: filteredServerIds };
  }

  function handleKeyDown(event: ReactKeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      if (!isSending && draft.trim()) {
        onSend(resolveSendOptions());
      }
    }
  }

  function handleSubmit() {
    if (!isSending && draft.trim()) {
      onSend(resolveSendOptions());
    }
  }

  async function handleUpdateConfig(newConfig: Partial<AppConfig>) {
    setIsUpdatingConfig(true);
    setConfigError("");
    try {
      const updated = await updateConfig(newConfig);
      applyConfigForMcpSelection(updated);
    } catch (error) {
      setConfigError(error instanceof Error ? error.message : "更新配置失败");
    } finally {
      setIsUpdatingConfig(false);
    }
  }

  async function handleOpenMcpServerSelector() {
    if (hasLoadedMcpServerSelection || isLoadingMcpServerSelection) {
      return;
    }

    setIsLoadingMcpServerSelection(true);
    setMcpServerSelectionError("");
    try {
      const loadedConfig = await fetchConfig();
      applyConfigForMcpSelection(loadedConfig);
      setSelectedMcpServerIds((prev) => prev ?? listEnabledMcpServerIds(loadedConfig));
    } catch (error) {
      setMcpServerSelectionError(error instanceof Error ? error.message : "加载 MCP Server 失败");
    } finally {
      setIsLoadingMcpServerSelection(false);
    }
  }

  function handleToggleMcpServerSelection(serverId: string) {
    const enabledServerIds = listEnabledMcpServerIds(config);
    if (!enabledServerIds.includes(serverId)) {
      return;
    }

    setMcpServerSelectionError("");
    setSelectedMcpServerIds((prev) => {
      const current = prev ?? enabledServerIds;
      const currentSet = new Set(current);
      if (currentSet.has(serverId)) {
        currentSet.delete(serverId);
      } else {
        currentSet.add(serverId);
      }
      return enabledServerIds.filter((item) => currentSet.has(item));
    });
  }

  async function handleAddOrUpdateFolderPermission(path: string, accessLevel: FolderAccessLevel) {
    const normalizedPath = path.trim();
    if (!normalizedPath) {
      setFolderPermissionsError("请输入文件夹绝对路径");
      throw new Error("请输入文件夹绝对路径");
    }

    setIsUpdatingFolderPermissions(true);
    setFolderPermissionsError("");
    try {
      const updated = await upsertChatFolderPermission(normalizedPath, accessLevel);
      setFolderPermissions(updated.permissions);
    } catch (error) {
      const message = error instanceof Error ? error.message : "更新文件夹权限失败";
      setFolderPermissionsError(message);
      throw error instanceof Error ? error : new Error(message);
    } finally {
      setIsUpdatingFolderPermissions(false);
    }
  }

  async function handleRemoveFolderPermission(path: string) {
    setIsUpdatingFolderPermissions(true);
    setFolderPermissionsError("");
    try {
      const updated = await removeChatFolderPermission(path);
      setFolderPermissions(updated.permissions);
    } catch (error) {
      const message = error instanceof Error ? error.message : "移除文件夹权限失败";
      setFolderPermissionsError(message);
      throw error instanceof Error ? error : new Error(message);
    } finally {
      setIsUpdatingFolderPermissions(false);
    }
  }

  async function handleToggleTestingMode(testingMode: boolean) {
    setIsUpdatingDataEnvironment(true);
    setDataEnvironmentError("");
    setDataOperationMessage("");
    try {
      const updated = await updateDataEnvironmentStatus({
        testing_mode: testingMode,
        backup_before_switch: true,
      });
      setDataEnvironment(updated);
      if (updated.switch_backup_path) {
        setDataOperationMessage(`已自动备份: ${updated.switch_backup_path}`);
      } else {
        setDataOperationMessage(testingMode ? "已切换到测试隔离环境" : "已切回默认数据环境");
      }
      await loadConfigAndFolderPermissions();
    } catch (error) {
      setDataEnvironmentError(error instanceof Error ? error.message : "切换数据环境失败");
    } finally {
      setIsUpdatingDataEnvironment(false);
    }
  }

  async function handleCreateDataBackup(backupPath?: string) {
    setIsCreatingDataBackup(true);
    setDataEnvironmentError("");
    setDataOperationMessage("");
    try {
      const payloadPath = backupPath?.trim();
      const result = await createDataBackup(payloadPath ? { backup_path: payloadPath } : {});
      setDataOperationMessage(`备份已创建: ${result.backup_path}`);
      await loadConfigAndFolderPermissions();
    } catch (error) {
      setDataEnvironmentError(error instanceof Error ? error.message : "创建备份失败");
    } finally {
      setIsCreatingDataBackup(false);
    }
  }

  async function handleImportDataBackup(backupPath: string) {
    const normalizedPath = backupPath.trim();
    if (!normalizedPath) {
      setDataEnvironmentError("请输入备份文件路径");
      return;
    }

    setIsImportingDataBackup(true);
    setDataEnvironmentError("");
    setDataOperationMessage("");
    try {
      const result = await importDataBackup({
        backup_path: normalizedPath,
        make_pre_import_backup: true,
      });
      if (result.pre_import_backup_path) {
        setDataOperationMessage(
          `导入成功，导入前备份: ${result.pre_import_backup_path}`,
        );
      } else {
        setDataOperationMessage("导入成功");
      }
      await loadConfigAndFolderPermissions();
    } catch (error) {
      setDataEnvironmentError(error instanceof Error ? error.message : "导入备份失败");
    } finally {
      setIsImportingDataBackup(false);
    }
  }

  return {
    textareaRef,
    messagesEndRef,
    messagesContainerRef,
    relationship,
    showMemoryContext,
    showConfigPanel,
    config,
    isUpdatingConfig,
    configError,
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
    toggleMemoryContext,
    toggleConfigPanel: () => {
      if (showConfigPanel) {
        setShowConfigPanel(false);
        return;
      }
      setShowConfigPanel(true);
      void loadConfigAndFolderPermissions();
    },
    closeConfigPanel: () => setShowConfigPanel(false),
    handleAddOrUpdateFolderPermission,
    handleRemoveFolderPermission,
    handleToggleTestingMode,
    handleCreateDataBackup,
    handleImportDataBackup,
    handleKeyDown,
    handleSubmit,
    handleUpdateConfig,
    mcpEnabled: Boolean(config.chat_mcp_enabled),
    availableMcpServers: Array.isArray(config.chat_mcp_servers) ? config.chat_mcp_servers : [],
    selectedMcpServerIds,
    isLoadingMcpServerSelection,
    mcpServerSelectionError,
    handleOpenMcpServerSelector,
    handleToggleMcpServerSelection,
  };
}
