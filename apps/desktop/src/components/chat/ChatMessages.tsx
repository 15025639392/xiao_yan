import { memo, useState } from "react";
import type { RelationshipSummary } from "../../lib/api";
import { MarkdownMessage } from "../MarkdownMessage";
import { Button } from "../ui";
import { getChatMessageDisplayState } from "./chatMessagePresentation";
import type { ChatEntry } from "./chatTypes";
import { ChatKnowledgeContext } from "./ChatKnowledgeContext";
import { ChatMemoryContext } from "./ChatMemoryContext";

type ChatMessagesProps = {
  assistantName: string;
  messages: ChatEntry[];
  relationship: RelationshipSummary | null;
  isSending: boolean;
  showMemoryContext: Set<string>;
  onToggleMemoryContext: (messageId: string) => void;
  onResume?: (message: ChatEntry) => void;
  onRetry?: (message: ChatEntry) => void;
  onDraftChange: (value: string) => void;
};

export const ChatMessages = memo(function ChatMessages({
  assistantName,
  messages,
  isSending,
  showMemoryContext,
  onToggleMemoryContext,
  onResume,
  onRetry,
  onDraftChange,
}: ChatMessagesProps) {
  const [showKnowledgeContext, setShowKnowledgeContext] = useState<Set<string>>(new Set());
  const latestUserIndex = findLatestUserIndex(messages);
  const hasAssistantAfterLatestUser =
    latestUserIndex >= 0 && messages.slice(latestUserIndex + 1).some((message) => message.role === "assistant");

  function toggleKnowledgeContext(messageId: string) {
    setShowKnowledgeContext((prev) => {
      const next = new Set(prev);
      if (next.has(messageId)) {
        next.delete(messageId);
      } else {
        next.add(messageId);
      }
      return next;
    });
  }

  if (messages.length === 0) {
    return (
      <div className="chat-page__empty">
        <div className="chat-page__empty-icon">💬</div>
        <p className="chat-page__empty-title">和{assistantName}说说现在的事</p>
        <p className="chat-page__empty-desc">可以从今天的安排、当下的情绪，或者你刚冒出来的念头开始。</p>
        <div className="chat-page__quick-actions">
          <Button
            className="chat-page__quick-btn"
            variant="secondary"
            onClick={() => onDraftChange("小晏，陪我理一下今天最该先做的事")}
            type="button"
          >
            理一理今天
          </Button>
          <Button
            className="chat-page__quick-btn"
            variant="secondary"
            onClick={() => onDraftChange("我现在有点乱，陪我一起捋一下")}
            type="button"
          >
            陪我捋一捋
          </Button>
        </div>
      </div>
    );
  }

  return (
    <>
      {messages.map((message) => (
        (() => {
          const display = getChatMessageDisplayState(message, assistantName);
          const messageKey = getChatMessageRenderKey(message);
          const hasBody = display.bodyMode !== "none";
          const hasDetails = Boolean(display.status || display.showKnowledgeContext);

          return (
            <article
              key={messageKey}
              className={`chat-message chat-message--${message.role} ${message.state === "failed" ? "chat-message--failed" : ""}`}
            >
              <div className="chat-message__bubble">
                {hasBody ? (
                  <div className={`chat-message__body chat-message__body--${display.bodyMode}`}>
                    {display.bodyMode === "markdown" ? (
                      <div className="chat-message__markdown">
                        <MarkdownMessage
                          content={message.state === "streaming" ? `${message.content}▍` : message.content}
                        />
                      </div>
                    ) : null}

                    {display.bodyMode === "streaming-placeholder" ? (
                      <div className="chat-message__streaming-placeholder" aria-live="polite">
                        <div className="chat-message__dots" aria-hidden="true">
                          <span />
                          <span />
                          <span />
                        </div>
                        <p className="chat-message__placeholder-text">{assistantName}正在整理这句话。</p>
                      </div>
                    ) : null}

                    {display.bodyMode === "plain-text" ? (
                      <p className="chat-message__content">{message.content}</p>
                    ) : null}
                  </div>
                ) : null}

                {hasDetails ? (
                  <div className={`chat-message__details ${hasBody ? "chat-message__details--with-body" : ""}`}>
                    {display.status ? (
                      <div
                        className={`chat-message__status chat-message__status--${display.status.tone}`}
                        aria-live="polite"
                      >
                        <span className="chat-message__status-dot" aria-hidden="true" />
                        <span>{display.status.text}</span>
                      </div>
                    ) : null}

                    {display.showKnowledgeContext ? (
                      <ChatKnowledgeContext
                        references={message.knowledgeReferences ?? []}
                        isExpanded={showKnowledgeContext.has(message.id)}
                        onToggle={() => toggleKnowledgeContext(message.id)}
                      />
                    ) : null}
                  </div>
                ) : null}
              </div>

              {display.showMemoryContext ? (
                <ChatMemoryContext
                  memories={message.relatedMemories ?? []}
                  isExpanded={showMemoryContext.has(message.id)}
                  onToggle={() => onToggleMemoryContext(message.id)}
                />
              ) : null}

              {display.showResumeAction ? (
                <div className="chat-message__actions">
                  <Button
                    className="chat-page__action-btn"
                    variant="secondary"
                    onClick={() => onResume?.(message)}
                    type="button"
                    disabled={isSending}
                  >
                    接着说完
                  </Button>
                </div>
              ) : null}

              {display.showRetryAction ? (
                <div className="chat-message__actions">
                  <Button
                    className="chat-page__action-btn"
                    variant="secondary"
                    onClick={() => onRetry?.(message)}
                    type="button"
                    disabled={isSending}
                  >
                    重新发送
                  </Button>
                </div>
              ) : null}
            </article>
          );
        })()
      ))}

      {isSending && latestUserIndex >= 0 && !hasAssistantAfterLatestUser ? (
        <article className="chat-message chat-message--loading">
          <div className="chat-message__bubble chat-message__bubble--loading">
            <div className="chat-message__loading-body" aria-live="polite">
              <div className="chat-message__dots" aria-hidden="true">
                <span />
                <span />
                <span />
              </div>
              <p className="chat-message__placeholder-text">{assistantName}正在整理这句话。</p>
            </div>
          </div>
        </article>
      ) : null}
    </>
  );
});

ChatMessages.displayName = "ChatMessages";

function getChatMessageRenderKey(message: ChatEntry): string {
  if (message.requestKey) {
    return `${message.role}:${message.requestKey}`;
  }

  return `${message.role}:${message.id}`;
}

function findLatestUserIndex(messages: ChatEntry[]): number {
  for (let index = messages.length - 1; index >= 0; index -= 1) {
    if (messages[index].role === "user") {
      return index;
    }
  }

  return -1;
}
