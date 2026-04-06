import { useEffect, useRef, useState } from "react";
import type { KeyboardEvent as ReactKeyboardEvent, RefObject } from "react";
import type { AppConfig } from "../../lib/api";
import { fetchConfig, updateConfig } from "../../lib/api";
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
  showMemoryContext: Set<string>;
  showConfigPanel: boolean;
  config: AppConfig;
  isUpdatingConfig: boolean;
  configError: string;
  toggleMemoryContext: (messageId: string) => void;
  toggleConfigPanel: () => void;
  closeConfigPanel: () => void;
  handleKeyDown: (event: ReactKeyboardEvent<HTMLTextAreaElement>) => void;
  handleSubmit: () => void;
  handleUpdateConfig: (newConfig: Partial<AppConfig>) => Promise<void>;
};

export function useChatPanelState({ draft, messages, isSending, onSend }: UseChatPanelStateArgs): UseChatPanelStateResult {
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const messagesContainerRef = useRef<HTMLDivElement>(null);

  const [showMemoryContext, setShowMemoryContext] = useState<Set<string>>(new Set());
  const [showConfigPanel, setShowConfigPanel] = useState(false);
  const [config, setConfig] = useState<AppConfig>({ chat_context_limit: 6 });
  const [isUpdatingConfig, setIsUpdatingConfig] = useState(false);
  const [configError, setConfigError] = useState("");

  useEffect(() => {
    async function loadConfig() {
      try {
        const data = await fetchConfig();
        setConfig(data);
      } catch (error) {
        console.error("加载配置失败:", error);
      }
    }
    void loadConfig();
  }, []);

  useEffect(() => {
    const textarea = textareaRef.current;
    if (!textarea) return;
    textarea.style.height = "auto";
    textarea.style.height = `${Math.min(textarea.scrollHeight, 200)}px`;
  }, [draft]);

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

  return {
    textareaRef,
    messagesEndRef,
    messagesContainerRef,
    showMemoryContext,
    showConfigPanel,
    config,
    isUpdatingConfig,
    configError,
    toggleMemoryContext,
    toggleConfigPanel: () => setShowConfigPanel((prev) => !prev),
    closeConfigPanel: () => setShowConfigPanel(false),
    handleKeyDown,
    handleSubmit,
    handleUpdateConfig,
  };
}
