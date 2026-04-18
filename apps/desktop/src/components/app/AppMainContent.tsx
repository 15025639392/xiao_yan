import { ChatPanel } from "../ChatPanel";
import type { ChatEntry, ChatSendOptions } from "../ChatPanel";
import { PersonaPanel } from "../PersonaPanel";
import { ToolPanel } from "../ToolPanel";
import type {
  BeingState,
  FocusContext,
  Goal,
  InnerWorldState,
  MacConsoleBootstrapStatus,
  PersonaProfile,
} from "../../lib/api";
import type { AppRoute } from "../../lib/appRoutes";
import { OverviewPanel } from "../../pages/OverviewPage";
import { CapabilitiesPage } from "../../pages/CapabilitiesPage";
import { MemoryPage } from "../../pages/MemoryPage";

type AppMainContentProps = {
  assistantName: string;
  attachedFiles: string[];
  attachedFolders: string[];
  attachedImages: string[];
  draft: string;
  focusGoalTitle: string | null;
  focusContext: FocusContext | null;
  focusTransitionHint: string | null;
  focusContextSummary: string | null;
  goals: Goal[];
  isAwake: boolean;
  isSending: boolean;
  macConsoleStatus: MacConsoleBootstrapStatus | null;
  messages: ChatEntry[];
  persona: PersonaProfile | null;
  petVisible: boolean;
  route: AppRoute;
  state: BeingState;
  world: InnerWorldState | null;
  onCompleteGoal: (goalId: string) => void;
  onDraftChange: (value: string) => void;
  onNavigate: (route: AppRoute) => void;
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
  onSetPetEnabled: (enabled: boolean) => void;
  onUpdateGoalStatus: (goalId: string, status: Goal["status"]) => void;
  renderFocusModeLabel: (focusMode: BeingState["focus_mode"]) => string;
};

export function AppMainContent({
  assistantName,
  attachedFiles,
  attachedFolders,
  attachedImages,
  draft,
  focusGoalTitle,
  focusContext,
  focusTransitionHint,
  focusContextSummary,
  goals,
  isAwake,
  isSending,
  macConsoleStatus,
  messages,
  persona,
  petVisible,
  route,
  state,
  world,
  onCompleteGoal,
  onDraftChange,
  onNavigate,
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
  onSetPetEnabled,
  onUpdateGoalStatus,
  renderFocusModeLabel,
}: AppMainContentProps) {
  if (route === "chat") {
    return (
      <ChatPanel
        assistantName={assistantName}
        draft={draft}
        focusGoalTitle={focusGoalTitle}
        focusContext={focusContext}
        focusTransitionHint={focusTransitionHint}
        focusContextSummary={focusContextSummary}
        focusEffort={state.focus_effort}
        focusModeLabel={renderFocusModeLabel(state.focus_mode)}
        isSending={isSending}
        messages={messages}
        attachedFolders={attachedFolders}
        attachedFiles={attachedFiles}
        attachedImages={attachedImages}
        modeLabel={isAwake ? "运行中" : "休眠中"}
        todayPlan={state.today_plan}
        activeGoals={goals.filter((goal) => goal.status === "active")}
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
        onCompleteGoal={onCompleteGoal}
      />
    );
  }

  if (route === "persona") {
    return (
      <PersonaPanel
        onPersonaUpdated={onPersonaUpdated}
        assistantName={assistantName}
        petEnabled={persona?.features?.avatar_enabled ?? false}
        petVisible={petVisible}
        onSetPetEnabled={onSetPetEnabled}
      />
    );
  }

  if (route === "memory") {
    return <MemoryPage assistantName={assistantName} />;
  }

  if (route === "tools") {
    return <ToolPanel />;
  }

  if (route === "capabilities") {
    return <CapabilitiesPage />;
  }

  return (
    <OverviewPanel
      focusGoalTitle={focusGoalTitle}
      focusContext={focusContext}
      focusTransitionHint={focusTransitionHint}
      focusContextSummary={focusContextSummary}
      goals={goals}
      latestActionLabel={state.last_action ? `${state.last_action.command} -> ${state.last_action.output}` : null}
      mode={state.mode}
      onUpdateGoalStatus={onUpdateGoalStatus}
      state={state}
      world={world}
      macConsoleStatus={macConsoleStatus}
      onNavigate={onNavigate}
    />
  );
}
