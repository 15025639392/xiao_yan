import { memo, useMemo } from "react";
import type { RelationshipSummary } from "../../lib/api";
import { MarkdownMessage } from "../MarkdownMessage";
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
        <p className="chat-page__empty-title">开始对话</p>
        <p className="chat-page__empty-desc">在下方输入框输入消息，与{assistantName}开始交流</p>
        <div className="chat-page__quick-actions">
          <button
            className="chat-page__quick-btn"
            onClick={() => onDraftChange("帮我制定今天的计划")}
            type="button"
          >
            制定今日计划
          </button>
          <button
            className="chat-page__quick-btn"
            onClick={() => onDraftChange("总结一下我们刚才聊的内容")}
            type="button"
          >
            总结对话
          </button>
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
              <div className="chat-message__markdown">
                <MarkdownMessage
                  content={message.state === "streaming" ? `${message.content}▍` : message.content}
                />
              </div>
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
            <button
              className="chat-page__action-btn"
              onClick={() => onResume?.(message)}
              type="button"
              disabled={isSending}
            >
              继续生成
            </button>
          ) : null}

          {message.role === "user" && message.state === "failed" ? (
            <button
              className="chat-page__action-btn"
              onClick={() => onRetry?.(message)}
              type="button"
              disabled={isSending}
            >
              重发
            </button>
          ) : null}
        </article>
      ))}

      {isSending && !messages.some((message) => message.role === "assistant" && message.state === "streaming") ? (
        <article className="chat-message chat-message--loading">
          <div className="chat-message__bubble chat-message__bubble--loading">
            <div className="chat-message__dots">
              <span />
              <span />
              <span />
            </div>
          </div>
        </article>
      ) : null}
    </>
  );
});

ChatMessages.displayName = "ChatMessages";
