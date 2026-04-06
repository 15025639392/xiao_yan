import type { Goal, TodayPlan } from "../lib/api";
import { ChatConfigPanel } from "./chat/ChatConfigPanel";
import { ChatHeader } from "./chat/ChatHeader";
import { ChatInputForm } from "./chat/ChatInputForm";
import { ChatMessages } from "./chat/ChatMessages";
import type { ChatEntry } from "./chat/chatTypes";
import { useChatPanelState } from "./chat/useChatPanelState";

export type { ChatEntry } from "./chat/chatTypes";

type ChatPanelProps = {
  assistantName?: string;
  draft: string;
  focusGoalTitle?: string | null;
  focusModeLabel: string;
  messages: ChatEntry[];
  isSending: boolean;
  todayPlan?: TodayPlan | null;
  activeGoals?: Goal[];
  modeLabel: string;
  onDraftChange: (value: string) => void;
  onSend: () => void;
  onResume?: (message: ChatEntry) => void;
  onCompleteGoal?: (goalId: string) => Promise<void>;
};

export function ChatPanel({
  assistantName = "小晏",
  draft,
  focusGoalTitle,
  messages,
  isSending,
  todayPlan,
  activeGoals,
  onDraftChange,
  onSend,
  onResume,
  onCompleteGoal,
}: ChatPanelProps) {
  const {
    textareaRef,
    messagesEndRef,
    messagesContainerRef,
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
    toggleConfigPanel,
    closeConfigPanel,
    handleAddOrUpdateFolderPermission,
    handleRemoveFolderPermission,
    handleKeyDown,
    handleSubmit,
    handleUpdateConfig,
  } = useChatPanelState({ draft, messages, isSending, onSend });

  return (
    <section className="chat-page">
      <ChatHeader
        focusGoalTitle={focusGoalTitle}
        todayPlan={todayPlan}
        activeGoals={activeGoals}
        onCompleteGoal={onCompleteGoal}
        onToggleConfig={toggleConfigPanel}
      />

      {showConfigPanel ? (
        <ChatConfigPanel
          config={config}
          isUpdating={isUpdatingConfig}
          error={configError}
          folderPermissions={folderPermissions}
          isUpdatingFolderPermissions={isUpdatingFolderPermissions}
          folderPermissionsError={folderPermissionsError}
          chatModelProviders={chatModelProviders}
          chatModelsError={chatModelsError}
          onAddOrUpdateFolderPermission={handleAddOrUpdateFolderPermission}
          onRemoveFolderPermission={handleRemoveFolderPermission}
          onUpdate={handleUpdateConfig}
          onClose={closeConfigPanel}
        />
      ) : null}

      <div ref={messagesContainerRef} className="chat-page__messages">
        <ChatMessages
          assistantName={assistantName}
          messages={messages}
          isSending={isSending}
          showMemoryContext={showMemoryContext}
          onToggleMemoryContext={toggleMemoryContext}
          onResume={onResume}
          onDraftChange={onDraftChange}
        />
        <div ref={messagesEndRef} />
      </div>

      <ChatInputForm
        draft={draft}
        isSending={isSending}
        textareaRef={textareaRef}
        onDraftChange={onDraftChange}
        onKeyDown={handleKeyDown}
        onSubmit={handleSubmit}
      />
    </section>
  );
}
