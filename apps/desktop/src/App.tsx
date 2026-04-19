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
import type { BeingState, PersonaProfile } from "./lib/api";
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
  last_action: null,
};

export default function App() {
  const [state, setState] = useState<BeingState>(initialState);
  const [messages, setMessages] = useState<ChatEntry[]>([]);
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
  } = useFocusPresentation(state);
  const assistantName = persona?.name?.trim() || "小晏";
  const assistantIdentity = persona?.identity?.trim() || "AI Agent Desktop";

  useAppRuntimeSync({
    messagesRef,
    pendingRequestMessageRef,
    setError,
    setIsSending,
    setMessages,
    setPersona,
    setState,
  });
  useChatRouteMessages({ route, setMessages });
  const {
    handlePersonaUpdated,
  } = useAppStateMutations({
    setError,
    setMessages,
    setState,
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

  return (
    <div className="app-layout">
      <AppSidebar
        assistantName={assistantName}
        route={route}
        showBrandMenu={showBrandMenu}
        theme={theme}
        onNavigate={handleNavigate}
        onShowBrandMenuChange={setShowBrandMenu}
        onToggleTheme={() => setTheme(theme === "dark" ? "light" : "dark")}
        onShowAbout={() => setShowAbout(true)}
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
          isSending={isSending}
          messages={messages}
          persona={persona}
          petVisible={petVisible}
          route={route}
          state={state}
          onDraftChange={setDraft}
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
