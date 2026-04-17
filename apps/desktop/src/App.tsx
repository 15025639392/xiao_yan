import { useCallback, useEffect, useRef, useState } from "react";

import type { ChatEntry, ChatSendOptions } from "./components/ChatPanel";
import { AboutDialog } from "./components/app/AboutDialog";
import { AppMainContent } from "./components/app/AppMainContent";
import { AppSidebar } from "./components/app/AppSidebar";
import type { PendingChatRequest } from "./components/app/chatRequestKey";
import { syncMessagesFromRuntime } from "./components/app/chatRuntimeMessages";
import { useAppChrome } from "./components/app/useAppChrome";
import { useChatAttachments } from "./components/app/useChatAttachments";
import { useChatComposer } from "./components/app/useChatComposer";
import { useDesktopPet } from "./components/app/useDesktopPet";
import type {
  BeingState,
  Goal,
  InnerWorldState,
  MacConsoleBootstrapStatus,
  PersonaProfile,
} from "./lib/api";
import {
  fetchGoals,
  fetchMessages,
  fetchState,
  fetchWorld,
  sleep,
  upsertChatFolderPermission,
  updateGoalStatus,
  wake,
} from "./lib/api";
import { subscribeAppRealtime } from "./lib/realtime";
import { startCapabilityWorker } from "./lib/capabilities/worker";
import {
  appendAssistantDelta,
  finalizeAssistantMessage,
  markAssistantMessageFailed,
  upsertAssistantMessage,
} from "./lib/chatMessages";
import {
  buildFolderPermissionPlan,
  loadImportedProjectRegistry,
} from "./lib/projects";

const initialState: BeingState = {
  mode: "sleeping",
  focus_mode: "sleeping",
  current_thought: null,
  active_goal_ids: [],
  today_plan: null,
  last_action: null,
};

export default function App() {
  const [state, setState] = useState<BeingState>(initialState);
  const [world, setWorld] = useState<InnerWorldState | null>(null);
  const [macConsoleStatus, setMacConsoleStatus] = useState<MacConsoleBootstrapStatus | null>(null);
  const [messages, setMessages] = useState<ChatEntry[]>([]);
  const [goals, setGoals] = useState<Goal[]>([]);
  const [persona, setPersona] = useState<PersonaProfile | null>(null);
  const [draft, setDraft] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState("");
  const pendingRequestMessageRef = useRef<PendingChatRequest | null>(null);
  const importedProjectRegistryRef = useRef(loadImportedProjectRegistry());
  const {
    route,
    theme,
    showAbout,
    setShowAbout,
    showBrandMenu,
    setShowBrandMenu,
    handleNavigate,
  } = useAppChrome();
  const {
    attachedFiles,
    attachedFolders,
    attachedImages,
    handlePickChatFiles,
    handlePickChatFolder,
    handlePickChatImages,
    handleRemoveAttachedFile,
    handleRemoveAttachedFolder,
    handleRemoveAttachedImage,
    setAttachedFiles,
    setAttachedFolders,
    setAttachedImages,
  } = useChatAttachments({ onError: setError });
  const clearAttachments = useCallback(() => {
    setAttachedFiles([]);
    setAttachedImages([]);
    setAttachedFolders([]);
  }, [setAttachedFiles, setAttachedImages, setAttachedFolders]);
  const restoreAttachments = useCallback(
    ({
      attachedFiles,
      attachedFolders,
      attachedImages,
    }: {
      attachedFiles: string[];
      attachedFolders: string[];
      attachedImages: string[];
    }) => {
      setAttachedFiles(attachedFiles);
      setAttachedImages(attachedImages);
      setAttachedFolders(attachedFolders);
    },
    [setAttachedFiles, setAttachedImages, setAttachedFolders],
  );
  const { handleResume, handleRetry, handleSend } = useChatComposer({
    attachedFiles,
    attachedFolders,
    attachedImages,
    clearAttachments,
    restoreAttachments,
    draft,
    pendingRequestMessageRef,
    setDraft,
    setError,
    setIsSending,
    setMessages,
  });
  const { petVisible, handlePetEnabledChange } = useDesktopPet({
    onError: setError,
    onPersonaChange: setPersona,
    persona,
  });
  const focusGoalTitle = resolveFocusGoalTitle(state, goals);
  const assistantName = persona?.name?.trim() || "小晏";
  const assistantIdentity = persona?.identity?.trim() || "AI Agent Desktop";

  useEffect(() => {
    const registry = importedProjectRegistryRef.current;
    if (registry.projects.length === 0) {
      return;
    }

    let cancelled = false;
    void restoreImportedProjectsToCore(registry).catch((err) => {
      if (cancelled) {
        return;
      }
      const detail = err instanceof Error ? err.message : "unknown error";
      setError(`恢复已导入项目权限失败: ${detail}`);
    });

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;

    async function syncRuntime() {
      try {
        const initialRoute = resolveRoute(window.location.hash);
        const [nextState, nextGoals, nextWorld] = await Promise.all([
          fetchState(),
          fetchGoals(),
          fetchWorld(),
        ]);

        if (cancelled) {
          return;
        }

        setState(nextState);
        setGoals(nextGoals.goals);
        setWorld(nextWorld);
        if (initialRoute === "chat") {
          void fetchMessages()
            .then((nextMessages) => {
              if (!cancelled) {
                setMessages((current) => syncMessagesFromRuntime(current, nextMessages.messages));
              }
            })
            .catch(() => {
              // Messages remain lazy-loaded when chat opens.
            });
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "同步失败");
        }
      }
    }

    void syncRuntime();
    const unsubscribe = subscribeAppRealtime((event) => {
      if (cancelled) {
        return;
      }

      if (event.type === "chat_started") {
        const pendingRequest = pendingRequestMessageRef.current;
        setMessages((current) =>
          upsertAssistantMessage(
            current,
            event.payload.assistant_message_id,
            "",
            "streaming",
            pendingRequest?.message,
            event.payload.sequence,
            undefined,
            event.payload.reasoning_session_id,
            event.payload.reasoning_state,
            event.payload.request_key ?? pendingRequest?.requestKey,
          )
        );
        pendingRequestMessageRef.current = null;
        setError("");
        return;
      }

      if (event.type === "chat_delta") {
        setMessages((current) => {
          const updated = appendAssistantDelta(
            current,
            event.payload.assistant_message_id,
            event.payload.delta,
            event.payload.sequence,
            event.payload.reasoning_session_id,
            event.payload.reasoning_state,
            event.payload.request_key,
          );
          return updated;
        });
        setError("");
        return;
      }

      if (event.type === "chat_completed") {
        setMessages((current) => {
          const updated = finalizeAssistantMessage(
            current,
            event.payload.assistant_message_id,
            event.payload.content,
            event.payload.sequence,
            event.payload.knowledge_references,
            event.payload.reasoning_session_id,
            event.payload.reasoning_state,
            event.payload.request_key,
          );
          return updated;
        });
        setError("");
        return;
      }

      if (event.type === "chat_failed") {
        setMessages((current) =>
          markAssistantMessageFailed(
            current,
            event.payload.assistant_message_id,
            event.payload.sequence,
            event.payload.reasoning_session_id,
            event.payload.reasoning_state,
            event.payload.error,
            event.payload.request_key,
          )
        );
        setError(event.payload.error);
        return;
      }

      const runtimePayload =
        event.type === "snapshot" ? event.payload.runtime : event.type === "runtime_updated" ? event.payload : null;
      if (!runtimePayload) {
        return;
      }

      setState(runtimePayload.state);
      setMessages((current) => syncMessagesFromRuntime(current, runtimePayload.messages));
      setGoals(runtimePayload.goals);
      setWorld(runtimePayload.world);
      if (runtimePayload.mac_console_status !== undefined) {
        setMacConsoleStatus(runtimePayload.mac_console_status ?? null);
      }
      setError("");
    });

    const unsubscribePersona = subscribeAppRealtime((event) => {
      if (cancelled) {
        return;
      }

      const personaPayload =
        event.type === "snapshot" ? event.payload.persona : event.type === "persona_updated" ? event.payload : null;
      if (!personaPayload) {
        return;
      }

      setPersona(personaPayload.profile);
    });

    return () => {
      cancelled = true;
      unsubscribe();
      unsubscribePersona();
    };
  }, []);

  useEffect(() => {
    if (route !== "chat") {
      return;
    }

    let cancelled = false;
    void fetchMessages()
      .then((nextMessages) => {
        if (!cancelled) {
          setMessages((current) => syncMessagesFromRuntime(current, nextMessages.messages));
        }
      })
      .catch((err) => {
        if (!cancelled) {
          console.error("加载聊天消息失败:", err);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [route]);

  // Desktop capability worker: pull pending capability requests from core and execute locally.
  useEffect(() => {
    const stop = startCapabilityWorker();
    return () => {
      stop();
    };
  }, []);

  async function handleWake() {
    try {
      setError("");
      setState(await wake());
    } catch (err) {
      setError(err instanceof Error ? err.message : "唤醒失败");
    }
  }

  async function handleSleep() {
    try {
      setError("");
      setState(await sleep());
    } catch (err) {
      setError(err instanceof Error ? err.message : "休眠失败");
    }
  }

  async function handleUpdateGoalStatus(goalId: string, status: Goal["status"]) {
    try {
      setError("");
      const updatedGoal = await updateGoalStatus(goalId, status);
      const refreshedState = await fetchState();

      setGoals((current) =>
        current.map((goal) => (goal.id === updatedGoal.id ? updatedGoal : goal))
      );
      setState(refreshedState);
    } catch (err) {
      setError(err instanceof Error ? err.message : "目标状态更新失败");
    }
  }

  async function handlePersonaUpdated() {
    try {
      const [nextState, nextMessages, nextGoals, nextWorld] = await Promise.all([
        fetchState(),
        fetchMessages(),
        fetchGoals(),
        fetchWorld(),
      ]);

      setState(nextState);
      setMessages(syncMessagesFromRuntime([], nextMessages.messages));
      setGoals(nextGoals.goals);
      setWorld(nextWorld);
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "同步失败");
    }
  }

  const isAwake = state.mode === "awake";

  return (
    <div className="app-layout">
      <AppSidebar
        assistantName={assistantName}
        isAwake={isAwake}
        mode={state.mode}
        route={route}
        showBrandMenu={showBrandMenu}
        theme={theme}
        onNavigate={handleNavigate}
        onShowBrandMenuChange={setShowBrandMenu}
        onToggleTheme={() => setTheme(theme === "dark" ? "light" : "dark")}
        onShowAbout={() => setShowAbout(true)}
        onWake={handleWake}
        onSleep={handleSleep}
      />

      {/* Main Content */}
      <main className="app-main">
        {/* Error Banner */}
        {error ? (
          <div className="error-banner">
            <strong>错误：</strong>
            {error}
          </div>
        ) : null}
        <AppMainContent
          assistantName={assistantName}
          attachedFiles={attachedFiles}
          attachedFolders={attachedFolders}
          attachedImages={attachedImages}
          draft={draft}
          focusGoalTitle={focusGoalTitle}
          goals={goals}
          isAwake={isAwake}
          isSending={isSending}
          macConsoleStatus={macConsoleStatus}
          messages={messages}
          persona={persona}
          petVisible={petVisible}
          route={route}
          state={state}
          world={world}
          onCompleteGoal={(goalId) => handleUpdateGoalStatus(goalId, "completed")}
          onDraftChange={setDraft}
          onNavigate={handleNavigate}
          onPersonaUpdated={() => {
            void handlePersonaUpdated();
          }}
          onPickFile={handlePickChatFiles}
          onPickFolder={handlePickChatFolder}
          onPickImage={handlePickChatImages}
          onRemoveAttachedFile={handleRemoveAttachedFile}
          onRemoveAttachedFolder={handleRemoveAttachedFolder}
          onRemoveAttachedImage={handleRemoveAttachedImage}
          onResume={handleResume}
          onRetry={handleRetry}
          onSend={handleSend}
          onSetPetEnabled={handlePetEnabledChange}
          onUpdateGoalStatus={handleUpdateGoalStatus}
          renderFocusModeLabel={renderFocusModeLabel}
        />

        <AboutDialog
          assistantIdentity={assistantIdentity}
          assistantName={assistantName}
          open={showAbout}
          onClose={() => setShowAbout(false)}
        />
      </main>
    </div>
  );
}

async function restoreImportedProjectsToCore(registry: ReturnType<typeof loadImportedProjectRegistry>) {
  const permissionPlan = buildFolderPermissionPlan(registry);
  for (const permission of permissionPlan) {
    await upsertChatFolderPermission(permission.path, permission.access_level);
  }
}


function resolveFocusGoalTitle(state: BeingState, goals: Goal[]): string | null {
  if (state.active_goal_ids.length > 0) {
    const currentGoal = goals.find((goal) => goal.id === state.active_goal_ids[0]);
    if (currentGoal) {
      return currentGoal.title;
    }
  }

  return state.today_plan?.goal_title ?? null;
}

function renderFocusModeLabel(focusMode: BeingState["focus_mode"]): string {
  if (focusMode === "morning_plan") {
    return "晨间计划";
  }
  if (focusMode === "autonomy") {
    return "常规自主";
  }
  if (focusMode === "sleeping") {
    return "休眠";
  }
  return "专注中";
}
