import type { KeyboardEvent as ReactKeyboardEvent, RefObject } from "react";
import type { RelationshipSummary } from "../../lib/api";
import { ChatResponseGuidance } from "./ChatResponseGuidance";
import { ChatRelationshipContext } from "./ChatRelationshipContext";
import { LoadingSpinner, SendIcon } from "./ChatIcons";

type ChatInputFormProps = {
  draft: string;
  isSending: boolean;
  attachedFolders?: string[];
  attachedFiles?: string[];
  attachedImages?: string[];
  relationship: RelationshipSummary | null;
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
};

export function ChatInputForm({
  draft,
  isSending,
  attachedFolders = [],
  attachedFiles = [],
  attachedImages = [],
  relationship,
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
}: ChatInputFormProps) {
  const totalAttachments = attachedFolders.length + attachedFiles.length + attachedImages.length;

  return (
    <div className="chat-page__input-area">
      <ChatRelationshipContext relationship={relationship} />
      <ChatResponseGuidance relationship={relationship} />

      <form
        className="chat-page__input-form"
        onSubmit={(event) => {
          event.preventDefault();
          onSubmit();
        }}
      >
        <div className="chat-page__input-toolbar">
          <button
            className={`chat-page__toolbar-btn ${attachedFolders.length > 0 ? "chat-page__toolbar-btn--active" : ""}`}
            type="button"
            aria-label="添加文件夹"
            title="添加文件夹"
            onClick={() => onPickFolder?.()}
            disabled={isSending}
          >
            📁
          </button>
          <button
            className={`chat-page__toolbar-btn ${attachedFiles.length > 0 ? "chat-page__toolbar-btn--active" : ""}`}
            type="button"
            aria-label="添加文件"
            title="添加文件"
            onClick={() => onPickFile?.()}
            disabled={isSending}
          >
            📄
          </button>
          <button
            className={`chat-page__toolbar-btn ${attachedImages.length > 0 ? "chat-page__toolbar-btn--active" : ""}`}
            type="button"
            aria-label="添加图片"
            title="添加图片"
            onClick={() => onPickImage?.()}
            disabled={isSending}
          >
            🖼️
          </button>
          {totalAttachments > 0 ? (
            <div className="chat-page__attached-folders" aria-label="已附加附件">
              {attachedFolders.map((path) => (
                <span key={path} className="chat-page__attached-folder-chip">
                  <span className="chat-page__attached-folder-type">📁</span>
                  <span className="chat-page__attached-folder-path">{path}</span>
                  <button
                    type="button"
                    className="chat-page__attached-folder-remove"
                    aria-label={`移除文件夹 ${path}`}
                    onClick={() => onRemoveAttachedFolder?.(path)}
                    disabled={isSending}
                  >
                    ×
                  </button>
                </span>
              ))}
              {attachedFiles.map((path) => (
                <span key={`file:${path}`} className="chat-page__attached-folder-chip">
                  <span className="chat-page__attached-folder-type">📄</span>
                  <span className="chat-page__attached-folder-path">{path}</span>
                  <button
                    type="button"
                    className="chat-page__attached-folder-remove"
                    aria-label={`移除文件 ${path}`}
                    onClick={() => onRemoveAttachedFile?.(path)}
                    disabled={isSending}
                  >
                    ×
                  </button>
                </span>
              ))}
              {attachedImages.map((path) => (
                <span key={`image:${path}`} className="chat-page__attached-folder-chip">
                  <span className="chat-page__attached-folder-type">🖼️</span>
                  <span className="chat-page__attached-folder-path">{path}</span>
                  <button
                    type="button"
                    className="chat-page__attached-folder-remove"
                    aria-label={`移除图片 ${path}`}
                    onClick={() => onRemoveAttachedImage?.(path)}
                    disabled={isSending}
                  >
                    ×
                  </button>
                </span>
              ))}
            </div>
          ) : null}
        </div>
        <label className="sr-only" htmlFor="chat-input">
          对话输入
        </label>
        <div className="chat-page__input-wrapper">
          <textarea
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
          <button className="chat-page__send-btn" type="submit" disabled={isSending || !draft.trim()} aria-label="发送">
            {isSending ? <LoadingSpinner /> : <SendIcon />}
          </button>
        </div>
        <div className="chat-page__input-hint">
          <span>Enter 发送 · Shift+Enter 换行</span>
        </div>
      </form>
    </div>
  );
}
