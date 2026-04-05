import { useRef, useEffect } from "react";

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
  latestActionLabel?: string | null;
  modeLabel: string;
  onDraftChange: (value: string) => void;
  onSend: () => void;
};

export function ChatPanel({
  draft,
  focusGoalTitle,
  focusModeLabel,
  messages,
  isSending,
  latestActionLabel,
  modeLabel,
  onDraftChange,
  onSend,
}: ChatPanelProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-resize textarea
  useEffect(() => {
    const textarea = textareaRef.current;
    if (textarea) {
      textarea.style.height = "auto";
      textarea.style.height = `${Math.min(textarea.scrollHeight, 200)}px`;
    }
  }, [draft]);

  function handleKeyDown(event: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      if (!isSending && draft.trim()) {
        onSend();
      }
    }
  }

  return (
    <section className="chat-stage">
      <div className="chat-container">
        {/* Main Chat Area */}
        <div className="panel chat-main">
          <div className="panel__header">
            <div className="panel__title-group">
              <div className="panel__icon">💬</div>
              <div>
                <h2 className="panel__title">对话</h2>
                <p className="panel__subtitle">与小晏实时交流</p>
              </div>
            </div>
            <span className={`status-badge ${isSending ? "status-badge--active" : "status-badge--awake"}`}>
              {isSending ? "思考中" : "在线"}
            </span>
          </div>

          <div className="chat-thread">
            {messages.length === 0 ? (
              <div className="empty-state empty-state--small">
                <p>还没有对话记录。</p>
                <p style={{ color: "var(--text-muted)", marginTop: "8px" }}>在下方输入框开始对话。</p>
              </div>
            ) : (
              messages.map((message) => (
                <article
                  key={message.id}
                  className={`chat-bubble chat-bubble--${message.role}`}
                >
                  <p className="chat-bubble__speaker">
                    {message.role === "user" ? "你" : "小晏"}
                  </p>
                  <p className="chat-bubble__content">{message.content}</p>
                </article>
              ))
            )}

            {/* Loading bubble */}
            {isSending && (
              <article className="chat-bubble chat-bubble--loading">
                <p className="chat-bubble__speaker">小晏</p>
                <div className="loading-dots">
                  <span className="loading-dots__dot" />
                  <span className="loading-dots__dot" />
                  <span className="loading-dots__dot" />
                </div>
              </article>
            )}
          </div>

          <div className="chat-composer">
            <form
              className="chat-composer__form"
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
              <div className="chat-composer__input-wrapper">
                <textarea
                  ref={textareaRef}
                  id="chat-input"
                  className="chat-composer__textarea"
                  value={draft}
                  placeholder="想和小晏说些什么？"
                  onChange={(event) => onDraftChange(event.target.value)}
                  onKeyDown={handleKeyDown}
                  rows={1}
                  disabled={isSending}
                />
                <span className="chat-composer__hint">Enter 发送 · Shift+Enter 换行</span>
              </div>
              <button
                className="btn btn--primary chat-composer__send"
                type="submit"
                disabled={isSending || !draft.trim()}
              >
                {isSending ? (
                  <>
                    <LoadingSpinner />
                    发送中
                  </>
                ) : (
                  <>
                    <SendIcon />
                    发送
                  </>
                )}
              </button>
            </form>
          </div>
        </div>

        {/* Sidebar */}
        <aside className="chat-sidebar">
          <div className="chat-sidebar__section">
            <h3 className="chat-sidebar__title">当前状态</h3>
            <div className="chat-sidebar__item">
              <span className="chat-sidebar__label">运行状态</span>
              <span className="chat-sidebar__value">{modeLabel}</span>
            </div>
            <div className="chat-sidebar__item">
              <span className="chat-sidebar__label">当前阶段</span>
              <span className="chat-sidebar__value">{focusModeLabel}</span>
            </div>
            <div className="chat-sidebar__item">
              <span className="chat-sidebar__label">当前焦点</span>
              <span className="chat-sidebar__value">{focusGoalTitle ?? "暂未锁定"}</span>
            </div>
          </div>

          {latestActionLabel && (
            <div className="chat-sidebar__section">
              <h3 className="chat-sidebar__title">最近动作</h3>
              <p style={{ margin: 0, fontSize: "0.8125rem", color: "var(--text-secondary)", lineHeight: 1.5 }}>
                {latestActionLabel}
              </p>
            </div>
          )}
        </aside>
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
