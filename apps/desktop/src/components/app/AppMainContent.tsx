import { ChatPanel } from "../ChatPanel";
import type { ChatEntry, ChatSendOptions } from "../ChatPanel";
import { PersonaPanel } from "../PersonaPanel";
import { ToolPanel } from "../ToolPanel";
import type {
  BeingState,
  FocusContext,
  PersonaProfile,
} from "../../lib/api";
import type { AppRoute } from "../../lib/appRoutes";
import { MemoryPage } from "../../pages/MemoryPage";
import { XiaohongshuPage } from "../../pages/XiaohongshuPage";
import { VrmGenerationPage } from "../../pages/VrmGenerationPage";

type AppMainContentProps = {
  assistantName: string;
  attachedFiles: string[];
  attachedFolders: string[];
  attachedImages: string[];
  draft: string;
  focusGoalTitle: string | null;
  focusContext: FocusContext | null;
  isSending: boolean;
  messages: ChatEntry[];
  persona: PersonaProfile | null;
  route: AppRoute;
  state: BeingState;
  onDraftChange: (value: string) => void;
  onPersonaUpdated: () => void;
  onPickFile: () => void;
  onPickFolder: () => void;
  onPickImage: () => void;
  onRemoveAttachedFile: (path: string) => void;
  onRemoveAttachedFolder: (path: string) => void;
  onRemoveAttachedImage: (path: string) => void;
  onResume: (message: ChatEntry) => void;
  onRetry: (message: ChatEntry) => void;
  onSend: (options?: ChatSendOptions) => void;
  onSetAvatarEnabled: (enabled: boolean) => void;
};

export function AppMainContent({
  assistantName,
  attachedFiles,
  attachedFolders,
  attachedImages,
  draft,
  focusGoalTitle,
  focusContext,
  isSending,
  messages,
  persona,
  route,
  state,
  onDraftChange,
  onPersonaUpdated,
  onPickFile,
  onPickFolder,
  onPickImage,
  onRemoveAttachedFile,
  onRemoveAttachedFolder,
  onRemoveAttachedImage,
  onResume,
  onRetry,
  onSend,
  onSetAvatarEnabled,
}: AppMainContentProps) {
  if (route === "persona") {
    return (
      <PersonaPanel
        onPersonaUpdated={onPersonaUpdated}
        assistantName={assistantName}
        avatarEnabled={persona?.features?.avatar_enabled ?? false}
        onSetAvatarEnabled={onSetAvatarEnabled}
      />
    );
  }

  if (route === "memory") {
    return <MemoryPage assistantName={assistantName} />;
  }

  if (route === "xiaohongshu") {
    return <XiaohongshuPage assistantName={assistantName} />;
  }

  if (route === "vrm-generation") {
    return <VrmGenerationPage assistantName={assistantName} />;
  }

  if (route === "tools") {
    return <ToolPanel />;
  }

  return (
    <ChatPanel
      assistantName={assistantName}
      draft={draft}
      focusGoalTitle={focusGoalTitle}
      focusContext={focusContext}
      focusSubject={state.focus_subject}
      focusEffort={state.focus_effort}
      isSending={isSending}
      messages={messages}
      attachedFolders={attachedFolders}
      attachedFiles={attachedFiles}
      attachedImages={attachedImages}
      onDraftChange={onDraftChange}
      onSend={onSend}
      onPickFolder={onPickFolder}
      onPickFile={onPickFile}
      onPickImage={onPickImage}
      onRemoveAttachedFolder={onRemoveAttachedFolder}
      onRemoveAttachedFile={onRemoveAttachedFile}
      onRemoveAttachedImage={onRemoveAttachedImage}
      onResume={onResume}
      onRetry={onRetry}
    />
  );
}
