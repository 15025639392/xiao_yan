import { useEffect, useRef, useState } from "react";
import type { KeyboardEvent as ReactKeyboardEvent, RefObject } from "react";
import type {
  AppConfig,
  ChatFolderPermission,
  ChatModelProviderItem,
  FolderAccessLevel,
  RelationshipSummary,
} from "../../lib/api";
import {
  DEFAULT_CHAT_PROVIDER,
  DEFAULT_CHAT_MODEL,
  fetchChatModels,
  fetchChatFolderPermissions,
  fetchConfig,
  fetchMemorySummary,
  removeChatFolderPermission,
  updateConfig,
  upsertChatFolderPermission,
} from "../../lib/api";
import { subscribeAppRealtime } from "../../lib/realtime";
import type { ChatEntry } from "./chatTypes";
import { useChatScrollBehavior } from "./useChatScrollBehavior";

type UseChatPanelStateArgs = {
  draft: string;
  messages: ChatEntry[];
  isSending: boolean;
  onSend: () => void;
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
  toggleMemoryContext: (messageId: string) => void;
  toggleConfigPanel: () => void;
  closeConfigPanel: () => void;
  handleAddOrUpdateFolderPermission: (path: string, accessLevel: FolderAccessLevel) => Promise<void>;
  handleRemoveFolderPermission: (path: string) => Promise<void>;
  handleKeyDown: (event: ReactKeyboardEvent<HTMLTextAreaElement>) => void;
  handleSubmit: () => void;
  handleUpdateConfig: (newConfig: Partial<AppConfig>) => Promise<void>;
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
  });
  const [isUpdatingConfig, setIsUpdatingConfig] = useState(false);
  const [configError, setConfigError] = useState("");
  const [folderPermissions, setFolderPermissions] = useState<ChatFolderPermission[]>([]);
  const [isUpdatingFolderPermissions, setIsUpdatingFolderPermissions] = useState(false);
  const [folderPermissionsError, setFolderPermissionsError] = useState("");
  const [chatModelProviders, setChatModelProviders] = useState<ChatModelProviderItem[]>([]);
  const [chatModelsError, setChatModelsError] = useState("");

  async function loadConfigAndFolderPermissions() {
    setConfigError("");
    setFolderPermissionsError("");
    setChatModelsError("");

    const [configResult, permissionsResult, modelsResult] = await Promise.allSettled([
      fetchConfig(),
      fetchChatFolderPermissions(),
      fetchChatModels(),
    ]);

    if (configResult.status === "fulfilled") {
      setConfig(configResult.value);
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

  function toggleMemoryContext(messageId: string) {
    setShowMemoryContext((prev) => {
      const next = new Set(prev);
      if (next.has(messageId)) {
        next.delete(messageId);
      } else {
        next.add(messageId);
      }
      return next;
    });
  }

  function handleKeyDown(event: ReactKeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      if (!isSending && draft.trim()) {
        onSend();
      }
    }
  }

  function handleSubmit() {
    if (!isSending && draft.trim()) {
      onSend();
    }
  }

  async function handleUpdateConfig(newConfig: Partial<AppConfig>) {
    setIsUpdatingConfig(true);
    setConfigError("");
    try {
      const updated = await updateConfig(newConfig);
      setConfig(updated);
    } catch (error) {
      setConfigError(error instanceof Error ? error.message : "更新配置失败");
    } finally {
      setIsUpdatingConfig(false);
    }
  }

  async function handleAddOrUpdateFolderPermission(path: string, accessLevel: FolderAccessLevel) {
    const normalizedPath = path.trim();
    if (!normalizedPath) {
      setFolderPermissionsError("请输入文件夹绝对路径");
      return;
    }

    setIsUpdatingFolderPermissions(true);
    setFolderPermissionsError("");
    try {
      const updated = await upsertChatFolderPermission(normalizedPath, accessLevel);
      setFolderPermissions(updated.permissions);
    } catch (error) {
      setFolderPermissionsError(error instanceof Error ? error.message : "更新文件夹权限失败");
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
      setFolderPermissionsError(error instanceof Error ? error.message : "移除文件夹权限失败");
    } finally {
      setIsUpdatingFolderPermissions(false);
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
    handleKeyDown,
    handleSubmit,
    handleUpdateConfig,
  };
}
