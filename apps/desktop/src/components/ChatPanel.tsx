import { useRef, useEffect, useState } from "react";
import type { TodayPlan, Goal, MemoryEntryDisplay, AppConfig } from "../lib/api";
import { MarkdownMessage } from "./MarkdownMessage";
import { fetchConfig, updateConfig } from "../lib/api";

export type ChatEntry = {
  id: string;
  role: "user" | "assistant";
  content: string;
  state?: "streaming" | "failed";
  requestMessage?: string;
  relatedMemories?: MemoryEntryDisplay[];
};

type ChatPanelProps = {
  assistantName?: string;
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
  onResume?: (message: ChatEntry) => void;
  onCompleteGoal?: (goalId: string) => Promise<void>;
};

export function ChatPanel({
  assistantName = "小晏",
  draft,
  focusGoalTitle,
  messages,
  isSending,
  todayPlan,
  activeGoals,
  onDraftChange,
  onSend,
  onResume,
  onCompleteGoal,
}: ChatPanelProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const [showMemoryContext, setShowMemoryContext] = useState<Set<string>>(new Set());
  const [showConfigPanel, setShowConfigPanel] = useState(false);
  const [config, setConfig] = useState<AppConfig>({ chat_context_limit: 6 });
  const [isUpdatingConfig, setIsUpdatingConfig] = useState(false);
  const [configError, setConfigError] = useState("");

  // 加载配置
  useEffect(() => {
    async function loadConfig() {
      try {
        const data = await fetchConfig();
        setConfig(data);
      } catch (err) {
        console.error("加载配置失败:", err);
      }
    }
    loadConfig();
  }, []);

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

  async function handleUpdateConfig(newConfig: Partial<AppConfig>) {
    setIsUpdatingConfig(true);
    setConfigError("");

    try {
      const updated = await updateConfig(newConfig);
      setConfig(updated);
    } catch (err) {
      setConfigError(err instanceof Error ? err.message : "更新配置失败");
    } finally {
      setIsUpdatingConfig(false);
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
          <button
            className="chat-page__action-btn"
            onClick={() => setShowConfigPanel(!showConfigPanel)}
            type="button"
            title="配置"
          >
            ⚙️ 配置
          </button>
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

      {/* 配置面板 */}
      {showConfigPanel && (
        <ConfigPanel
          config={config}
          isUpdating={isUpdatingConfig}
          error={configError}
          onUpdate={handleUpdateConfig}
          onClose={() => setShowConfigPanel(false)}
        />
      )}

      {/* Messages */}
      <div className="chat-page__messages">
        {messages.length === 0 ? (
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
        ) : (
          <>
            {messages.map((message) => (
              <article
                key={message.id}
                className={`chat-message chat-message--${message.role} ${message.state === "failed" ? "chat-message--failed" : ""}`}
              >
                <div className="chat-message__bubble">
                  {message.role === "assistant" ? (
                    <div className="chat-message__markdown">
                      <MarkdownMessage content={message.state === "streaming" ? `${message.content}▍` : message.content} />
                    </div>
                  ) : (
                    <p className="chat-message__content">{message.content}</p>
                  )}
                </div>

                {/* 记忆上下文（可选显示） */}
                {message.role === "assistant" && message.relatedMemories && message.relatedMemories.length > 0 && (
                  <MemoryContext
                    memories={message.relatedMemories}
                    isExpanded={showMemoryContext.has(message.id)}
                    onToggle={() => toggleMemoryContext(message.id)}
                  />
                )}

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
              </article>
            ))}
            {isSending && !messages.some((message) => message.role === "assistant" && message.state === "streaming") && (
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

  // ═══════════════════════════════════════════════════
  // 组件内部辅助函数
  // ═══════════════════════════════════════════════════

  function toggleMemoryContext(messageId: string) {
    setShowMemoryContext((prev) => {
      const next = new Set(prev);
      if (next.has(messageId)) {
        next.delete(messageId);
      } else {
        next.add(messageId);
      }
      return next;
    });
  }
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

// ═══════════════════════════════════════════════════
// 情绪徽章组件
// ═══════════════════════════════════════════════════

function EmotionBadge({ emotion }: { emotion: EmotionState | null }) {
  if (!emotion) return null;

  const emotionConfig = getEmotionDisplay(emotion.primary_emotion, emotion.primary_intensity);

  return (
    <div
      className="emotion-badge"
      style={{ color: emotionConfig.color, borderColor: emotionConfig.color }}
    >
      <span className="emotion-badge__emoji">{emotionConfig.emoji}</span>
      <span className="emotion-badge__label">{emotionConfig.label}</span>
      {emotion.primary_intensity !== "none" && (
        <span className="emotion-badge__intensity">
          {getIntensityLabel(emotion.primary_intensity)}
        </span>
      )}
      {emotion.secondary_emotion && (
        <>
          <span className="emotion-badge__divider">·</span>
          <span className="emotion-badge__secondary">
            {getEmotionDisplay(emotion.secondary_emotion, emotion.secondary_intensity).emoji}
          </span>
        </>
      )}
    </div>
  );
}

function getEmotionDisplay(emotion: string, intensity: string): {
  emoji: string;
  label: string;
  color: string;
} {
  const map: Record<string, { emoji: string; label: string; color: string }> = {
    joy: { emoji: "😊", label: "开心", color: "#10b981" },
    sadness: { emoji: "😢", label: "难过", color: "#6b7280" },
    anger: { emoji: "😠", label: "生气", color: "#ef4444" },
    fear: { emoji: "😨", label: "害怕", color: "#8b5cf6" },
    surprise: { emoji: "😲", label: "惊讶", color: "#f59e0b" },
    disgust: { emoji: "🤢", label: "厌恶", color: "#84cc16" },
    calm: { emoji: "😌", label: "平静", color: "#3b82f6" },
    lonely: { emoji: "🥺", label: "孤独", color: "#6366f1" },
    grateful: { emoji: "🙏", label: "感激", color: "#ec4899" },
    frustrated: { emoji: "😤", label: "沮丧", color: "#f97316" },
    proud: { emoji: "😎", label: "自豪", color: "#14b8a6" },
    engaged: { emoji: "🤔", label: "专注", color: "#0ea5e9" },
  };
  return map[emotion] || { emoji: "😐", label: emotion, color: "#9ca3af" };
}

function getIntensityLabel(intensity: string): string {
  const map: Record<string, string> = {
    none: "",
    mild: "轻微",
    moderate: "中等",
    strong: "强烈",
    intense: "极强",
  };
  return map[intensity] || "";
}

// ═══════════════════════════════════════════════════
// 记忆上下文组件
// ═══════════════════════════════════════════════════

function MemoryContext({
  memories,
  isExpanded,
  onToggle,
}: {
  memories: MemoryEntryDisplay[];
  isExpanded: boolean;
  onToggle: () => void;
}) {
  return (
    <div className="chat-message__memory-context">
      <button
        type="button"
        className="chat-message__memory-toggle"
        onClick={onToggle}
      >
        <span className="chat-message__memory-icon">📚</span>
        <span className="chat-message__memory-label">
          相关记忆 ({memories.length})
        </span>
        <span
          className={`chat-message__memory-chevron ${isExpanded ? 'chat-message__memory-chevron--expanded' : ''}`}
        >
          ▼
        </span>
      </button>

      {isExpanded && (
        <div className="chat-message__memory-list">
          {memories.map((memory, index) => (
            <div key={memory.id} className="chat-message__memory-item">
              <div className="chat-message__memory-header">
                <span className={`chat-message__memory-kind chat-message__memory-kind--${memory.kind}`}>
                  {getKindLabel(memory.kind)}
                </span>
                {memory.starred && (
                  <span className="chat-message__memory-starred">⭐</span>
                )}
              </div>
              <p className="chat-message__memory-content">{memory.content}</p>
              <div className="chat-message__memory-footer">
                <span className={`chat-message__memory-strength chat-message__memory-strength--${memory.strength}`}>
                  {getStrengthLabel(memory.strength)}
                </span>
                {memory.created_at && (
                  <span className="chat-message__memory-date">
                    {formatDate(memory.created_at)}
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function getKindLabel(kind: string): string {
  const map: Record<string, string> = {
    fact: "事实",
    episodic: "事件",
    semantic: "语义",
    emotional: "情感",
    chat_raw: "对话",
  };
  return map[kind] || kind;
}

function getStrengthLabel(strength: string): string {
  const map: Record<string, string> = {
    faint: "微弱",
    weak: "薄弱",
    normal: "普通",
    vivid: "清晰",
    core: "核心",
  };
  return map[strength] || strength;
}

function formatDate(dateString: string): string {
  const date = new Date(dateString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);

  if (diffMins < 1) return "刚刚";
  if (diffMins < 60) return `${diffMins}分钟前`;
  if (diffHours < 24) return `${diffHours}小时前`;
  if (diffDays < 7) return `${diffDays}天前`;
  return date.toLocaleDateString("zh-CN");
}

// ═══════════════════════════════════════════════════
// 配置面板组件
// ═══════════════════════════════════════════════════

function ConfigPanel({
  config,
  isUpdating,
  error,
  onUpdate,
  onClose,
}: {
  config: AppConfig;
  isUpdating: boolean;
  error: string;
  onUpdate: (config: Partial<AppConfig>) => void;
  onClose: () => void;
}) {
  return (
    <div className="config-panel-overlay" onClick={onClose}>
      <div className="config-panel" onClick={(e) => e.stopPropagation()}>
        <div className="config-panel__header">
          <h3 className="config-panel__title">配置</h3>
          <button
            type="button"
            className="config-panel__close"
            onClick={onClose}
          >
            ×
          </button>
        </div>

        <div className="config-panel__body">
          {/* 聊天上下文限制 */}
          <div className="config-panel__section">
            <label className="config-panel__label">
              聊天上下文限制
            </label>
            <p className="config-panel__description">
              每次聊天时携带的相关事件数量。值越小响应越快，但连贯性可能降低；值越大对话越连贯，但响应可能变慢。
            </p>
            <div className="config-panel__control">
              <input
                type="range"
                min="1"
                max="20"
                value={config.chat_context_limit}
                onChange={(e) => {
                  const value = parseInt(e.target.value, 10);
                  if (!isUpdating) {
                    onUpdate({ chat_context_limit: value });
                  }
                }}
                disabled={isUpdating}
                className="config-panel__slider"
              />
              <span className="config-panel__value">
                {config.chat_context_limit}
              </span>
            </div>
            <div className="config-panel__presets">
              <button
                type="button"
                className={`config-panel__preset ${config.chat_context_limit === 3 ? 'config-panel__preset--active' : ''}`}
                onClick={() => !isUpdating && onUpdate({ chat_context_limit: 3 })}
                disabled={isUpdating}
              >
                保守 (3)
              </button>
              <button
                type="button"
                className={`config-panel__preset ${config.chat_context_limit === 6 ? 'config-panel__preset--active' : ''}`}
                onClick={() => !isUpdating && onUpdate({ chat_context_limit: 6 })}
                disabled={isUpdating}
              >
                默认 (6)
              </button>
              <button
                type="button"
                className={`config-panel__preset ${config.chat_context_limit === 10 ? 'config-panel__preset--active' : ''}`}
                onClick={() => !isUpdating && onUpdate({ chat_context_limit: 10 })}
                disabled={isUpdating}
              >
                开放 (10)
              </button>
            </div>
          </div>
        </div>

        {/* 错误提示 */}
        {error && (
          <div className="config-panel__error">
            {error}
          </div>
        )}

        <div className="config-panel__footer">
          <button
            type="button"
            className="config-panel__btn config-panel__btn--primary"
            onClick={onClose}
          >
            完成
          </button>
        </div>
      </div>
    </div>
  );
}
