import { useCallback, useEffect, useRef, useState } from "react";
import type { KeyboardEvent as ReactKeyboardEvent, RefObject } from "react";
import type {
  AppConfig,
  ChatModelProviderItem,
} from "../../lib/api";
import {
  DEFAULT_CHAT_PROVIDER,
  DEFAULT_CHAT_MODEL,
  fetchChatModels,
  fetchConfig,
  updateConfig,
} from "../../lib/api";
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
  showMemoryContext: Set<string>;
  showConfigPanel: boolean;
  config: AppConfig;
  isUpdatingConfig: boolean;
  configError: string;
  chatModelProviders: ChatModelProviderItem[];
  chatModelsError: string;
  toggleMemoryContext: (messageId: string) => void;
  toggleConfigPanel: () => void;
  closeConfigPanel: () => void;
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

  const [showMemoryContext, setShowMemoryContext] = useState<Set<string>>(new Set());
  const [showConfigPanel, setShowConfigPanel] = useState(false);
  const [config, setConfig] = useState<AppConfig>({
    chat_context_limit: 6,
    chat_provider: DEFAULT_CHAT_PROVIDER,
    chat_model: DEFAULT_CHAT_MODEL,
    chat_read_timeout_seconds: 180,
    chat_continuous_reasoning_enabled: true,
    chat_mcp_enabled: false,
    chat_mcp_servers: [],
  });
  const [isUpdatingConfig, setIsUpdatingConfig] = useState(false);
  const [configError, setConfigError] = useState("");
  const [chatModelProviders, setChatModelProviders] = useState<ChatModelProviderItem[]>([]);
  const [chatModelsError, setChatModelsError] = useState("");
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

  async function loadConfigPanelData() {
    setConfigError("");
    setChatModelsError("");

    const [configResult, modelsResult] = await Promise.allSettled([
      fetchConfig(),
      fetchChatModels(),
    ]);

    if (configResult.status === "fulfilled") {
      setMcpServerSelectionError("");
      applyConfigForMcpSelection(configResult.value);
    } else {
      const message = configResult.reason instanceof Error ? configResult.reason.message : "加载配置失败";
      setConfigError(message);
      console.error("加载配置失败:", configResult.reason);
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
    let cancelled = false;
    fetchConfig()
      .then((loadedConfig) => {
        if (cancelled) {
          return;
        }
        // Bootstrap chat-level config (e.g. continuous reasoning) without touching MCP selection state.
        setConfig(loadedConfig);
      })
      .catch(() => {
        // Keep default chat config when bootstrap fetch fails.
      });

    return () => {
      cancelled = true;
    };
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
    const options: ChatSendOptions = {};
    if (selectedMcpServerIds !== null) {
      const enabledServerIdSet = new Set(listEnabledMcpServerIds(config));
      const filteredServerIds = selectedMcpServerIds.filter((serverId) => enabledServerIdSet.has(serverId));
      options.mcpServerIds = filteredServerIds;
    }
    if (config.chat_continuous_reasoning_enabled) {
      options.continuousReasoningEnabled = true;
      const latestReasoningSessionId = [...messages]
        .reverse()
        .find((message) => message.role === "assistant" && typeof message.reasoningSessionId === "string")
        ?.reasoningSessionId;
      if (latestReasoningSessionId) {
        options.reasoningSessionId = latestReasoningSessionId;
      }
    }
    return Object.keys(options).length > 0 ? options : undefined;
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

  return {
    textareaRef,
    messagesEndRef,
    messagesContainerRef,
    showMemoryContext,
    showConfigPanel,
    config,
    isUpdatingConfig,
    configError,
    chatModelProviders,
    chatModelsError,
    toggleMemoryContext,
    toggleConfigPanel: () => {
      if (showConfigPanel) {
        setShowConfigPanel(false);
        return;
      }
      setShowConfigPanel(true);
      void loadConfigPanelData();
    },
    closeConfigPanel: () => setShowConfigPanel(false),
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
