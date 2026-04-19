import type { FocusContext, FocusEffort, FocusSubject } from "../lib/api";
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
  focusContext?: FocusContext | null;
  focusSubject?: FocusSubject | null;
  focusEffort?: FocusEffort | null;
  messages: ChatEntry[];
  attachedFolders?: string[];
  attachedFiles?: string[];
  attachedImages?: string[];
  isSending: boolean;
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
};

export function ChatPanel({
  assistantName = "小晏",
  draft,
  focusGoalTitle,
  focusContext,
  focusSubject,
  focusEffort,
  messages,
  attachedFolders = [],
  attachedFiles = [],
  attachedImages = [],
  isSending,
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
        focusContext={focusContext}
        focusSubject={focusSubject}
        focusEffort={focusEffort}
        onToggleConfig={toggleConfigPanel}
      />

      {showConfigPanel ? (
        <ChatConfigPanel
          config={config}
          isUpdating={isUpdatingConfig}
          error={configError}
          chatModelProviders={chatModelProviders}
          chatModelsError={chatModelsError}
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
