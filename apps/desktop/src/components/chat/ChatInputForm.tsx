import { useState } from "react";
import type { KeyboardEvent as ReactKeyboardEvent, RefObject } from "react";
import type { ChatMcpServerConfig } from "../../lib/api";
import { Button, Checkbox, Textarea } from "../ui";
import { LoadingSpinner, SendIcon } from "./ChatIcons";

type ChatInputFormProps = {
  draft: string;
  isSending: boolean;
  attachedFolders?: string[];
  attachedFiles?: string[];
  attachedImages?: string[];
  textareaRef: RefObject<HTMLTextAreaElement>;
  onDraftChange: (value: string) => void;
  onPickFolder?: () => void;
  onPickFile?: () => void;
  onPickImage?: () => void;
  onRemoveAttachedFolder?: (path: string) => void;
  onRemoveAttachedFile?: (path: string) => void;
  onRemoveAttachedImage?: (path: string) => void;
  onKeyDown: (event: ReactKeyboardEvent<HTMLTextAreaElement>) => void;
  onSubmit: () => void;
  mcpEnabled: boolean;
  mcpServers: ChatMcpServerConfig[];
  selectedMcpServerIds: string[] | null;
  isLoadingMcpServers: boolean;
  mcpServerError: string;
  onOpenMcpSelector: () => void;
  onToggleMcpServer: (serverId: string) => void;
};

export function ChatInputForm({
  draft,
  isSending,
  attachedFolders = [],
  attachedFiles = [],
  attachedImages = [],
  textareaRef,
  onDraftChange,
  onPickFolder,
  onPickFile,
  onPickImage,
  onRemoveAttachedFolder,
  onRemoveAttachedFile,
  onRemoveAttachedImage,
  onKeyDown,
  onSubmit,
  mcpEnabled,
  mcpServers,
  selectedMcpServerIds,
  isLoadingMcpServers,
  mcpServerError,
  onOpenMcpSelector,
  onToggleMcpServer,
}: ChatInputFormProps) {
  const [showMcpSelector, setShowMcpSelector] = useState(false);
  const totalAttachments = attachedFolders.length + attachedFiles.length + attachedImages.length;
  const enabledMcpServers = mcpServers.filter((server) => server.enabled);
  const effectiveSelectedMcpServerIds = selectedMcpServerIds ?? [];
  const selectedMcpServerCount = effectiveSelectedMcpServerIds.length;
  const mcpServerCount = enabledMcpServers.length;
  const mcpToolbarLabel = mcpEnabled ? `MCP ${selectedMcpServerCount}/${mcpServerCount}` : "MCP 关";

  return (
    <div className="chat-page__input-area">
      <form
        className="chat-page__input-form"
        onSubmit={(event) => {
          event.preventDefault();
          onSubmit();
        }}
        >
        <div className="chat-page__input-toolbar">
          <Button
            variant="ghost"
            size="icon"
            className={`chat-page__toolbar-btn ${attachedFolders.length > 0 ? "chat-page__toolbar-btn--active" : ""}`}
            type="button"
            aria-label="添加文件夹"
            title="添加文件夹"
            onClick={() => onPickFolder?.()}
            disabled={isSending}
          >
            📁
          </Button>
          <Button
            variant="ghost"
            size="icon"
            className={`chat-page__toolbar-btn ${attachedFiles.length > 0 ? "chat-page__toolbar-btn--active" : ""}`}
            type="button"
            aria-label="添加文件"
            title="添加文件"
            onClick={() => onPickFile?.()}
            disabled={isSending}
          >
            📄
          </Button>
          <Button
            variant="ghost"
            size="icon"
            className={`chat-page__toolbar-btn ${attachedImages.length > 0 ? "chat-page__toolbar-btn--active" : ""}`}
            type="button"
            aria-label="添加图片"
            title="添加图片"
            onClick={() => onPickImage?.()}
            disabled={isSending}
          >
            🖼️
          </Button>
          <Button
            variant="ghost"
            className={`chat-page__toolbar-btn chat-page__toolbar-btn--text ${showMcpSelector ? "chat-page__toolbar-btn--active" : ""}`}
            type="button"
            aria-label="选择 MCP Servers"
            title="选择 MCP Servers"
            disabled={isSending}
            onClick={() => {
              const nextOpen = !showMcpSelector;
              setShowMcpSelector(nextOpen);
              if (nextOpen) {
                onOpenMcpSelector();
              }
            }}
          >
            🧩 {mcpToolbarLabel}
          </Button>
          {totalAttachments > 0 ? (
            <div className="chat-page__attached-folders" aria-label="已附加附件">
              {attachedFolders.map((path) => (
                <span key={path} className="chat-page__attached-folder-chip">
                  <span className="chat-page__attached-folder-type">📁</span>
                  <span className="chat-page__attached-folder-path">{path}</span>
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    className="chat-page__attached-folder-remove"
                    aria-label={`移除文件夹 ${path}`}
                    onClick={() => onRemoveAttachedFolder?.(path)}
                    disabled={isSending}
                  >
                    ×
                  </Button>
                </span>
              ))}
              {attachedFiles.map((path) => (
                <span key={`file:${path}`} className="chat-page__attached-folder-chip">
                  <span className="chat-page__attached-folder-type">📄</span>
                  <span className="chat-page__attached-folder-path">{path}</span>
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    className="chat-page__attached-folder-remove"
                    aria-label={`移除文件 ${path}`}
                    onClick={() => onRemoveAttachedFile?.(path)}
                    disabled={isSending}
                  >
                    ×
                  </Button>
                </span>
              ))}
              {attachedImages.map((path) => (
                <span key={`image:${path}`} className="chat-page__attached-folder-chip">
                  <span className="chat-page__attached-folder-type">🖼️</span>
                  <span className="chat-page__attached-folder-path">{path}</span>
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    className="chat-page__attached-folder-remove"
                    aria-label={`移除图片 ${path}`}
                    onClick={() => onRemoveAttachedImage?.(path)}
                    disabled={isSending}
                  >
                    ×
                  </Button>
                </span>
              ))}
            </div>
          ) : null}
        </div>
        {showMcpSelector ? (
          <div className="chat-page__mcp-selector" aria-label="MCP Servers 选择">
            {!mcpEnabled ? <div className="chat-page__mcp-hint">全局 MCP 未启用，请先在配置中开启。</div> : null}
            {mcpEnabled && isLoadingMcpServers ? <div className="chat-page__mcp-hint">加载 MCP Servers...</div> : null}
            {mcpEnabled && !isLoadingMcpServers && mcpServerCount === 0 ? (
              <div className="chat-page__mcp-hint">当前没有可用的 MCP Server。</div>
            ) : null}
            {mcpEnabled && !isLoadingMcpServers && mcpServerCount > 0 ? (
              <div className="chat-page__mcp-options">
                {enabledMcpServers.map((server) => (
                  <label key={server.server_id} className="chat-page__mcp-option">
                    <Checkbox
                      aria-label={`MCP Server ${server.server_id}`}
                      checked={effectiveSelectedMcpServerIds.includes(server.server_id)}
                      disabled={isSending}
                      onChange={() => onToggleMcpServer(server.server_id)}
                    />
                    <span>{server.server_id}</span>
                  </label>
                ))}
              </div>
            ) : null}
            {mcpServerError ? <div className="chat-page__mcp-error">{mcpServerError}</div> : null}
          </div>
        ) : null}
        <label className="sr-only" htmlFor="chat-input">
          对话输入
        </label>
        <div className="chat-page__input-wrapper">
          <Textarea
            ref={textareaRef}
            id="chat-input"
            className="chat-page__textarea"
            value={draft}
            placeholder="输入消息..."
            onChange={(event) => onDraftChange(event.target.value)}
            onKeyDown={onKeyDown}
            rows={1}
            disabled={isSending}
          />
          <Button className="chat-page__send-btn" type="submit" disabled={isSending || !draft.trim()} aria-label="发送">
            {isSending ? <LoadingSpinner /> : <SendIcon />}
          </Button>
        </div>
        <div className="chat-page__input-hint">
          <span>Enter 发送 · Shift+Enter 换行</span>
        </div>
      </form>
    </div>
  );
}
