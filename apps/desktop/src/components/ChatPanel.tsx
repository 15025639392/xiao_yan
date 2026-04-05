import { useRef, useEffect } from "react";
import type { TodayPlan, Goal } from "../lib/api";
import { MarkdownMessage } from "./MarkdownMessage";

export type ChatEntry = {
  id: string;
  role: "user" | "assistant";
  content: string;
};

type ChatPanelProps = {
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
  onCompleteGoal?: (goalId: string) => Promise<void>;
};

export function ChatPanel({
  draft,
  focusGoalTitle,
  messages,
  isSending,
  todayPlan,
  activeGoals,
  onDraftChange,
  onSend,
  onCompleteGoal,
}: ChatPanelProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Auto-resize textarea
  useEffect(() => {
    const textarea = textareaRef.current;
    if (textarea) {
      textarea.style.height = "auto";
      textarea.style.height = `${Math.min(textarea.scrollHeight, 200)}px`;
    }
  }, [draft]);

  // Auto-scroll to bottom
  useEffect(() => {
    if (messagesEndRef.current && typeof messagesEndRef.current.scrollIntoView === 'function') {
      try {
        messagesEndRef.current.scrollIntoView({ behavior: "smooth" });
      } catch {
        // 在测试环境中可能会失败，忽略错误
      }
    }
  }, [messages.length, isSending]);

  function handleKeyDown(event: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      if (!isSending && draft.trim()) {
        onSend();
      }
    }
  }

  return (
    <section className="chat-page">
      {/* Header */}
      <header className="chat-page__header">
        <div className="chat-page__header-info">
          <h2 className="chat-page__title">
            {focusGoalTitle ?? "自由对话"}
          </h2>
          {todayPlan && (
            <span className="chat-page__subtitle">
              今日计划: {todayPlan.steps.filter(s => s.status === "completed").length}/{todayPlan.steps.length} 完成
            </span>
          )}
        </div>
        <div className="chat-page__header-actions">
          {todayPlan?.steps.some(s => s.status === "pending") && activeGoals && activeGoals[0] && onCompleteGoal && (
            <button
              className="chat-page__action-btn"
              onClick={() => onCompleteGoal(activeGoals[0].id)}
              type="button"
            >
              <CheckIcon /> 完成目标
            </button>
          )}
        </div>
      </header>

      {/* Messages */}
      <div className="chat-page__messages">
        {messages.length === 0 ? (
          <div className="chat-page__empty">
            <div className="chat-page__empty-icon">💬</div>
            <p className="chat-page__empty-title">开始对话</p>
            <p className="chat-page__empty-desc">在下方输入框输入消息，与小晏开始交流</p>
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
        ) : (
          <>
            {messages.map((message) => (
              <article
                key={message.id}
                className={`chat-message chat-message--${message.role}`}
              >
                <div className="chat-message__bubble">
                  {message.role === "assistant" ? (
                    <div className="chat-message__markdown">
                      <MarkdownMessage content={message.content} />
                    </div>
                  ) : (
                    <p className="chat-message__content">{message.content}</p>
                  )}
                </div>
              </article>
            ))}
            {isSending && (
              <article className="chat-message chat-message--loading">
                <div className="chat-message__bubble chat-message__bubble--loading">
                  <div className="chat-message__dots">
                    <span />
                    <span />
                    <span />
                  </div>
                </div>
              </article>
            )}
            <div ref={messagesEndRef} />
          </>
        )}
      </div>

      {/* Input */}
      <div className="chat-page__input-area">
        <form
          className="chat-page__input-form"
          onSubmit={(e) => {
            e.preventDefault();
            if (!isSending && draft.trim()) {
              onSend();
            }
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
              onKeyDown={handleKeyDown}
              rows={1}
              disabled={isSending}
            />
            <button
              className="chat-page__send-btn"
              type="submit"
              disabled={isSending || !draft.trim()}
              aria-label="发送"
            >
              {isSending ? (
                <LoadingSpinner />
              ) : (
                <SendIcon />
              )}
            </button>
          </div>
          <div className="chat-page__input-hint">
            <span>Enter 发送 · Shift+Enter 换行</span>
          </div>
        </form>
      </div>
    </section>
  );
}

function SendIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <line x1="22" y1="2" x2="11" y2="13" />
      <polygon points="22 2 15 22 11 13 2 9 22 2" />
    </svg>
  );
}

function LoadingSpinner() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ animation: "spin 1s linear infinite" }}>
      <style>{`
        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
      `}</style>
      <path d="M21 12a9 9 0 1 1-6.219-8.56" />
    </svg>
  );
}

function TargetIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <circle cx="12" cy="12" r="10" />
      <circle cx="12" cy="12" r="6" />
      <circle cx="12" cy="12" r="2" />
    </svg>
  );
}

function CalendarIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
      <line x1="16" y1="2" x2="16" y2="6" />
      <line x1="8" y1="2" x2="8" y2="6" />
      <line x1="3" y1="10" x2="21" y2="10" />
    </svg>
  );
}

function ZapIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
    </svg>
  );
}

function CheckIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <polyline points="20 6 9 17 4 12" />
    </svg>
  );
}

function calculateProgress(goals: Goal[]): number {
  if (goals.length === 0) return 0;
  const completed = goals.filter(g => g.status === "completed").length;
  return Math.round((completed / goals.length) * 100);
}
