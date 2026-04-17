import { memo, useMemo } from "react";
import type { RelationshipSummary } from "../../lib/api";
import { MarkdownMessage } from "../MarkdownMessage";
import { Button } from "../ui";
import { getAssistantStatus, getUserFailedStatus } from "./chatMessagePresentation";
import type { ChatEntry } from "./chatTypes";
import { ChatMemoryContext } from "./ChatMemoryContext";
import { ChatMessageResponseReference } from "./ChatMessageResponseReference";

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
  relationship,
  isSending,
  showMemoryContext,
  onToggleMemoryContext,
  onResume,
  onRetry,
  onDraftChange,
}: ChatMessagesProps) {
  const latestAssistantMessageId = useMemo(
    () =>
      [...messages]
        .reverse()
        .find((message) => message.role === "assistant" && message.state !== "failed")?.id,
    [messages],
  );

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
        <article
          key={message.id}
          className={`chat-message chat-message--${message.role} ${message.state === "failed" ? "chat-message--failed" : ""}`}
        >
          <div className="chat-message__bubble">
            {message.role === "assistant" ? (
              <>
                {message.content ? (
                  <div className="chat-message__markdown">
                    <MarkdownMessage
                      content={message.state === "streaming" ? `${message.content}▍` : message.content}
                    />
                  </div>
                ) : message.state === "streaming" ? (
                  <div className="chat-message__streaming-placeholder" aria-live="polite">
                    <div className="chat-message__dots" aria-hidden="true">
                      <span />
                      <span />
                      <span />
                    </div>
                    <p className="chat-message__placeholder-text">{assistantName}正在整理这句话。</p>
                  </div>
                ) : null}

                {(() => {
                  const assistantStatus = getAssistantStatus(message, assistantName);
                  if (!assistantStatus) {
                    return null;
                  }

                  return (
                    <div
                      className={`chat-message__status chat-message__status--${assistantStatus.tone}`}
                      aria-live="polite"
                    >
                      <span className="chat-message__status-dot" aria-hidden="true" />
                      <span>{assistantStatus.text}</span>
                    </div>
                  );
                })()}
              </>
            ) : (
              <p className="chat-message__content">{message.content}</p>
            )}

            {message.role === "assistant" && message.id === latestAssistantMessageId ? (
              <ChatMessageResponseReference relationship={relationship} />
            ) : null}

            {message.role === "assistant" &&
            message.knowledgeReferences &&
            message.knowledgeReferences.length > 0 ? (
              <div className="chat-message__knowledge-references" aria-label="知识来源">
                <span className="chat-message__knowledge-title">知识来源</span>
                <ul className="chat-message__knowledge-list">
                  {message.knowledgeReferences.map((reference, index) => (
                    <li
                      key={`${message.id}-knowledge-reference-${index}`}
                      className="chat-message__knowledge-item"
                    >
                      <div className="chat-message__knowledge-head">
                        <span className="chat-message__knowledge-source">{reference.source}</span>
                        {typeof reference.similarity === "number" ? (
                          <span className="chat-message__knowledge-score">
                            相似度 {reference.similarity.toFixed(2)}
                          </span>
                        ) : null}
                      </div>
                      <span className="chat-message__knowledge-excerpt">{reference.excerpt}</span>
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}
          </div>

          {message.role === "assistant" &&
          message.relatedMemories &&
          message.relatedMemories.length > 0 ? (
            <ChatMemoryContext
              memories={message.relatedMemories}
              isExpanded={showMemoryContext.has(message.id)}
              onToggle={() => onToggleMemoryContext(message.id)}
            />
          ) : null}

          {message.role === "assistant" && message.state === "failed" && message.requestMessage ? (
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

          {message.role === "user" && message.state === "failed" ? (
            <div className="chat-message__actions">
              <div className="chat-message__status chat-message__status--failed" aria-live="polite">
                <span className="chat-message__status-dot" aria-hidden="true" />
                <span>{getUserFailedStatus(message, assistantName).text}</span>
              </div>
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
      ))}

      {isSending && !messages.some((message) => message.role === "assistant" && message.state === "streaming") ? (
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
