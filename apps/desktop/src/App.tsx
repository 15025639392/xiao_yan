import { useCallback, useEffect, useRef, useState } from "react";

import type { ChatEntry, ChatSendOptions } from "./components/ChatPanel";
import { AboutDialog } from "./components/app/AboutDialog";
import { AppMainContent } from "./components/app/AppMainContent";
import { AppSidebar } from "./components/app/AppSidebar";
import type { PendingChatRequest } from "./components/app/chatRequestKey";
import { useAppRuntimeSync } from "./components/app/useAppRuntimeSync";
import { useAppChrome } from "./components/app/useAppChrome";
import { useAppStateMutations } from "./components/app/useAppStateMutations";
import { useChatAttachments } from "./components/app/useChatAttachments";
import { useChatComposer } from "./components/app/useChatComposer";
import { useChatRouteMessages } from "./components/app/useChatRouteMessages";
import { useDesktopPet } from "./components/app/useDesktopPet";
import { useFocusPresentation } from "./components/app/useFocusPresentation";
import type {
  BeingState,
  Goal,
  InnerWorldState,
  MacConsoleBootstrapStatus,
  PersonaProfile,
} from "./lib/api";
import { upsertChatFolderPermission } from "./lib/api";
import { startCapabilityWorker } from "./lib/capabilities/worker";
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
  const messagesRef = useRef<ChatEntry[]>([]);
  const pendingRequestMessageRef = useRef<PendingChatRequest | null>(null);
  const importedProjectRegistryRef = useRef(loadImportedProjectRegistry());
  messagesRef.current = messages;
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
  const {
    focusContext,
    focusGoalTitle,
    focusContextSummary,
    focusTransitionHint,
    updateFocusTransitionHint,
  } = useFocusPresentation(state, goals);
  const assistantName = persona?.name?.trim() || "小晏";
  const assistantIdentity = persona?.identity?.trim() || "AI Agent Desktop";

  useAppRuntimeSync({
    messagesRef,
    pendingRequestMessageRef,
    setError,
    setGoals,
    setIsSending,
    setMacConsoleStatus,
    setMessages,
    setPersona,
    setState,
    setWorld,
    updateFocusTransitionHint,
  });
  useChatRouteMessages({ route, setMessages });
  const {
    handleWake,
    handleSleep,
    handleUpdateGoalStatus,
    handlePersonaUpdated,
  } = useAppStateMutations({
    setError,
    setGoals,
    setMessages,
    setState,
    setWorld,
    updateFocusTransitionHint,
  });

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

  // Desktop capability worker: pull pending capability requests from core and execute locally.
  useEffect(() => {
    const stop = startCapabilityWorker();
    return () => {
      stop();
    };
  }, []);

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
          focusContext={focusContext}
          focusTransitionHint={focusTransitionHint}
          focusContextSummary={focusContextSummary}
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
