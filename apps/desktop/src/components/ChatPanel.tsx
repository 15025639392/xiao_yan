import type { Goal, TodayPlan } from "../lib/api";
import { ChatConfigPanel } from "./chat/ChatConfigPanel";
import { ChatHeader } from "./chat/ChatHeader";
import { ChatInputForm } from "./chat/ChatInputForm";
import { ChatMessages } from "./chat/ChatMessages";
import type { ChatEntry, ChatSendOptions } from "./chat/chatTypes";
import { useChatPanelState } from "./chat/useChatPanelState";

export type { ChatEntry, ChatSendOptions } from "./chat/chatTypes";

type ChatPanelProps = {
  assistantName?: string;
  draft: string;
  focusGoalTitle?: string | null;
  focusModeLabel: string;
  messages: ChatEntry[];
  attachedFolders?: string[];
  attachedFiles?: string[];
  attachedImages?: string[];
  isSending: boolean;
  todayPlan?: TodayPlan | null;
  activeGoals?: Goal[];
  modeLabel: string;
  onDraftChange: (value: string) => void;
  onSend: (options?: ChatSendOptions) => void;
  onPickFolder?: () => void;
  onPickFile?: () => void;
  onPickImage?: () => void;
  onRemoveAttachedFolder?: (path: string) => void;
  onRemoveAttachedFile?: (path: string) => void;
  onRemoveAttachedImage?: (path: string) => void;
  onResume?: (message: ChatEntry) => void;
  onRetry?: (message: ChatEntry) => void;
  onCompleteGoal?: (goalId: string) => Promise<void>;
};

export function ChatPanel({
  assistantName = "小晏",
  draft,
  focusGoalTitle,
  messages,
  attachedFolders = [],
  attachedFiles = [],
  attachedImages = [],
  isSending,
  todayPlan,
  activeGoals,
  onDraftChange,
  onSend,
  onPickFolder,
  onPickFile,
  onPickImage,
  onRemoveAttachedFolder,
  onRemoveAttachedFile,
  onRemoveAttachedImage,
  onResume,
  onRetry,
  onCompleteGoal,
}: ChatPanelProps) {
  const {
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
    toggleConfigPanel,
    closeConfigPanel,
    handleAddOrUpdateFolderPermission,
    handleRemoveFolderPermission,
    handleToggleTestingMode,
    handleCreateDataBackup,
    handleImportDataBackup,
    handleKeyDown,
    handleSubmit,
    handleUpdateConfig,
    isLoadingMcpServerSelection,
    mcpServerSelectionError,
    selectedMcpServerIds,
    availableMcpServers,
    mcpEnabled,
    handleOpenMcpServerSelector,
    handleToggleMcpServerSelection,
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
          dataEnvironment={dataEnvironment}
          isUpdatingDataEnvironment={isUpdatingDataEnvironment}
          isCreatingDataBackup={isCreatingDataBackup}
          isImportingDataBackup={isImportingDataBackup}
          dataEnvironmentError={dataEnvironmentError}
          dataOperationMessage={dataOperationMessage}
          onAddOrUpdateFolderPermission={handleAddOrUpdateFolderPermission}
          onRemoveFolderPermission={handleRemoveFolderPermission}
          onToggleTestingMode={handleToggleTestingMode}
          onCreateDataBackup={handleCreateDataBackup}
          onImportDataBackup={handleImportDataBackup}
          onUpdate={handleUpdateConfig}
          onClose={closeConfigPanel}
        />
      ) : null}

      <div ref={messagesContainerRef} className="chat-page__messages">
        <ChatMessages
          assistantName={assistantName}
          messages={messages}
          relationship={relationship}
          isSending={isSending}
          showMemoryContext={showMemoryContext}
          onToggleMemoryContext={toggleMemoryContext}
          onResume={onResume}
          onRetry={onRetry}
          onDraftChange={onDraftChange}
        />
        <div ref={messagesEndRef} />
      </div>

      <ChatInputForm
        draft={draft}
        isSending={isSending}
        attachedFolders={attachedFolders}
        attachedFiles={attachedFiles}
        attachedImages={attachedImages}
        textareaRef={textareaRef}
        onDraftChange={onDraftChange}
        onPickFolder={onPickFolder}
        onPickFile={onPickFile}
        onPickImage={onPickImage}
        onRemoveAttachedFolder={onRemoveAttachedFolder}
        onRemoveAttachedFile={onRemoveAttachedFile}
        onRemoveAttachedImage={onRemoveAttachedImage}
        onKeyDown={handleKeyDown}
        onSubmit={handleSubmit}
        mcpEnabled={mcpEnabled}
        mcpServers={availableMcpServers}
        selectedMcpServerIds={selectedMcpServerIds}
        isLoadingMcpServers={isLoadingMcpServerSelection}
        mcpServerError={mcpServerSelectionError}
        onOpenMcpSelector={handleOpenMcpServerSelector}
        onToggleMcpServer={handleToggleMcpServerSelection}
      />
    </section>
  );
}
