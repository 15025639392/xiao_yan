import type { KeyboardEvent as ReactKeyboardEvent, RefObject } from "react";
import type { RelationshipSummary } from "../../lib/api";
import { ChatRelationshipContext } from "./ChatRelationshipContext";
import { LoadingSpinner, SendIcon } from "./ChatIcons";

type ChatInputFormProps = {
  draft: string;
  isSending: boolean;
  relationship: RelationshipSummary | null;
  textareaRef: RefObject<HTMLTextAreaElement>;
  onDraftChange: (value: string) => void;
  onKeyDown: (event: ReactKeyboardEvent<HTMLTextAreaElement>) => void;
  onSubmit: () => void;
};

export function ChatInputForm({
  draft,
  isSending,
  relationship,
  textareaRef,
  onDraftChange,
  onKeyDown,
  onSubmit,
}: ChatInputFormProps) {
  return (
    <div className="chat-page__input-area">
      <ChatRelationshipContext relationship={relationship} />

      <form
        className="chat-page__input-form"
        onSubmit={(event) => {
          event.preventDefault();
          onSubmit();
        }}
      >
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
