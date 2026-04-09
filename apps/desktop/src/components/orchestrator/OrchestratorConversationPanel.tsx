import { useEffect, useRef, useState, type KeyboardEvent as ReactKeyboardEvent } from "react";

import type { OrchestratorMessage, OrchestratorSession } from "../../lib/api";
import { useChatScrollBehavior } from "../chat/useChatScrollBehavior";
import { OrchestratorMessageRenderer } from "./OrchestratorMessageRenderer";

type OrchestratorConversationPanelProps = {
  session: OrchestratorSession;
  messages: OrchestratorMessage[];
  draft: string;
  isSending: boolean;
  onDraftChange: (value: string) => void;
  onSendMessage: () => void;
  onApprovePlan: (sessionId: string) => Promise<void>;
  onRejectPlan: (sessionId: string) => Promise<void>;
  onResumeSession: (sessionId: string) => Promise<void>;
  onCancelSession: (sessionId: string) => Promise<void>;
  onActivateSession: (sessionId: string) => Promise<void>;
  onSendQuickMessage: (message: string) => Promise<void> | void;
  onClearConsole: () => void;
  metrics: { total: number; done: number; running: number; failed: number };
  onToggleSidebar: () => void;
  sidebarOpen: boolean;
};

export function OrchestratorConversationPanel({
  session,
  messages,
  draft,
  isSending,
  onDraftChange,
  onSendMessage,
  onApprovePlan,
  onRejectPlan,
  onResumeSession,
  onCancelSession,
  onActivateSession,
  onSendQuickMessage,
  onClearConsole,
  metrics,
  onToggleSidebar,
  sidebarOpen,
}: OrchestratorConversationPanelProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const messagesContainerRef = useRef<HTMLDivElement>(null);
  const [showQuickCommands, setShowQuickCommands] = useState(false);

  useEffect(() => {
    const textarea = textareaRef.current;
    if (!textarea) {
      return;
    }
    textarea.style.height = "auto";
    textarea.style.height = `${Math.min(textarea.scrollHeight, 200)}px`;
  }, [draft]);

  useChatScrollBehavior({
    messages: messages.map((message) => ({
      id: message.message_id,
      role: message.role === "system" ? "assistant" : message.role,
      content: message.blocks.map((block) => block.text ?? "").join("\n\n"),
      state: message.state === "completed" ? undefined : message.state,
    })),
    isSending,
    messagesContainerRef,
    messagesEndRef,
  });

  function handleKeyDown(event: ReactKeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      if (!isSending && draft.trim()) {
        onSendMessage();
      }
    }
  }

  return (
    <section className="orchestrator-chat-shell">
      <OrchestratorLiveStatus
        session={session}
        isSending={isSending}
        onActivateSession={onActivateSession}
        onSendQuickMessage={onSendQuickMessage}
      />

      <div ref={messagesContainerRef} className="chat-page__messages orchestrator-chat-shell__messages">
        <div className="orchestrator-chat-context">
          <div className="orchestrator-chat-context__project">
            <span className="orchestrator-chat-context__name">{session.project_name}</span>
            <span className={`orchestrator-chat-context__status orchestrator-chat-context__status--${session.status}`}>
              {session.status === "pending_plan_approval" ? "待审批" :
               session.status === "running" ? "运行中" :
               session.status === "completed" ? "已完成" :
               session.status === "failed" ? "失败" : "草稿"}
            </span>
            {session.coordination?.queue_position ? (
              <span className="orchestrator-chat-context__queue">队列 #{session.coordination.queue_position}</span>
            ) : null}
          </div>
          
          <div className="orchestrator-chat-context__progress">
            <div className="orchestrator-progress-bar orchestrator-progress-bar--mini">
              <span style={{ width: `${metrics.total > 0 ? (metrics.done / metrics.total) * 100 : 0}%` }}></span>
            </div>
            <span className="orchestrator-chat-context__progress-text">{metrics.done}/{metrics.total || 0} 任务</span>
          </div>
          
          <div className="orchestrator-chat-context__actions">
            {messages.length > 0 ? (
              <button
                className="orchestrator-chat-context__action"
                onClick={onClearConsole}
                type="button"
                title="清空控制台内容"
                aria-label="清空控制台内容"
              >
                清空控制台
              </button>
            ) : null}
            <button
              className="orchestrator-chat-context__toggle"
              onClick={onToggleSidebar}
              type="button"
              title={sidebarOpen ? "收起高级信息" : "展开高级信息"}
              aria-label={sidebarOpen ? "收起高级信息" : "展开高级信息"}
            >
              {sidebarOpen ? "📊" : "📈"}
            </button>
          </div>
        </div>
        {messages.length === 0 ? (
          <div className="chat-page__empty">
            <div className="chat-page__empty-icon">🧭</div>
            <p className="chat-page__empty-title">主控会话已建立</p>
            <p className="chat-page__empty-desc">可以直接让小晏解释计划、推进任务或调整主控边界。</p>
            
            <div className="orchestrator-quick-actions">
              <button 
                className="orchestrator-quick-action" 
                onClick={() => void onSendQuickMessage("先解释当前推进到哪一步")}
                type="button"
              >
                📊 查看进度
              </button>
              <button 
                className="orchestrator-quick-action" 
                onClick={() => void onSendQuickMessage("显示所有任务")}
                type="button"
              >
                📋 任务列表
              </button>
            </div>
          </div>
        ) : (
          <>
            {showQuickCommands && (
              <div className="orchestrator-quick-commands-bar">
                <button 
                  className="orchestrator-quick-command-bar__item" 
                  onClick={() => {
                    void onSendQuickMessage("请检查当前进度并总结");
                    setShowQuickCommands(false);
                  }}
                  type="button"
                >
                  📊 进度总结
                </button>
                <button 
                  className="orchestrator-quick-command-bar__item" 
                  onClick={() => {
                    void onSendQuickMessage("请继续推进下一个任务");
                    setShowQuickCommands(false);
                  }}
                  type="button"
                >
                  🚀 继续推进
                </button>
                <button 
                  className="orchestrator-quick-command-bar__item" 
                  onClick={() => {
                    void onSendQuickMessage("请验证当前已完成的任务");
                    setShowQuickCommands(false);
                  }}
                  type="button"
                >
                  ✅ 验证任务
                </button>
                <button 
                  className="orchestrator-quick-command-bar__item" 
                  onClick={() => {
                    void onSendQuickMessage("请查看是否有错误或异常");
                    setShowQuickCommands(false);
                  }}
                  type="button"
                >
                  🔍 检查错误
                </button>
                <button 
                  className="orchestrator-quick-command-bar__item orchestrator-quick-command-bar__item--close"
                  onClick={() => setShowQuickCommands(false)}
                  type="button"
                  title="关闭"
                >
                  ✕
                </button>
              </div>
            )}
            
            {messages.map((message) => (
              <OrchestratorMessageRenderer
                key={message.message_id}
                message={message}
                session={session}
                onApprovePlan={onApprovePlan}
                onRejectPlan={onRejectPlan}
                onResumeSession={onResumeSession}
                onCancelSession={onCancelSession}
                onActivateSession={onActivateSession}
                onSendQuickMessage={onSendQuickMessage}
              />
            ))}
          </>
        )}
        <div ref={messagesEndRef} />
      </div>

      <div className="chat-page__input-area orchestrator-chat-shell__input">
        <div className="chat-page__input-toolbar">
          <button
            type="button"
            className={`chat-page__toolbar-btn ${showQuickCommands ? 'chat-page__toolbar-btn--active' : ''}`}
            onClick={() => setShowQuickCommands(!showQuickCommands)}
            title="快捷指令"
          >
            ⚡
          </button>
          <div className="chat-page__toolbar-divider"></div>
          <div className="orchestrator-prompt-chips orchestrator-prompt-chips--interactive" aria-label="主控输入建议">
            {[
              "先解释当前推进到哪一步",
              "批准计划并开工",
            ].map((preset) => (
              <button
                key={preset}
                type="button"
                className="orchestrator-prompt-chip-button"
                onClick={() => void onSendQuickMessage(preset)}
              >
                {preset}
              </button>
            ))}
          </div>
        </div>

        <form
          className="chat-page__input-form"
          onSubmit={(event) => {
            event.preventDefault();
            onSendMessage();
          }}
        >
          <label className="sr-only" htmlFor="orchestrator-chat-input">
            主控输入
          </label>
          <div className="chat-page__input-wrapper">
            <textarea
              ref={textareaRef}
              id="orchestrator-chat-input"
              className="chat-page__textarea"
              value={draft}
              placeholder="继续让小晏推进，或调整 scope / 验收 / 优先级"
              onChange={(event) => onDraftChange(event.target.value)}
              onKeyDown={handleKeyDown}
              rows={1}
              disabled={isSending}
            />
            <button className="chat-page__send-btn" type="submit" disabled={isSending || !draft.trim()} aria-label="发送主控消息">
              {isSending ? "..." : "↑"}
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

function OrchestratorLiveStatus({
  session,
  isSending,
  onActivateSession,
  onSendQuickMessage,
}: {
  session: OrchestratorSession;
  isSending: boolean;
  onActivateSession: (sessionId: string) => Promise<void>;
  onSendQuickMessage: (message: string) => Promise<void> | void;
}) {
  const status = resolveLiveStatus(session);
  const [pendingActionMessage, setPendingActionMessage] = useState<string | null>(null);
  const [pendingActivateSessionId, setPendingActivateSessionId] = useState<string | null>(null);
  if (!status) {
    return null;
  }

  async function handleFactAction(message: string) {
    if (isSending || pendingActionMessage) {
      return;
    }

    setPendingActionMessage(message);
    try {
      await Promise.resolve(onSendQuickMessage(message));
    } finally {
      setPendingActionMessage(null);
    }
  }

  async function handleActivateSession(sessionId: string) {
    if (pendingActivateSessionId || pendingActionMessage || isSending) {
      return;
    }

    setPendingActivateSessionId(sessionId);
    try {
      await onActivateSession(sessionId);
    } finally {
      setPendingActivateSessionId(null);
    }
  }

  return (
    <section
      className={`orchestrator-live-status orchestrator-live-status--${status.tone}`}
      aria-label="主控实时状态"
    >
      <div className="orchestrator-live-status__header">
        <div className="orchestrator-live-status__signal" aria-hidden="true" />
        <div className="orchestrator-live-status__copy">
          <p className="orchestrator-live-status__label">{status.label}</p>
          <strong>{status.title}</strong>
          <p>{status.detail}</p>
        </div>
        {status.badge ? <span className="orchestrator-pill">{status.badge}</span> : null}
        {status.action ? (
          <button
            type="button"
            className="chat-page__action-btn"
            disabled={pendingActivateSessionId !== null || pendingActionMessage !== null || isSending}
            onClick={() => void handleActivateSession(status.action!.sessionId)}
          >
            {pendingActivateSessionId === status.action.sessionId
              ? (status.action.pending_label ?? "切换中...")
              : status.action.label}
          </button>
        ) : null}
      </div>

      <div className="orchestrator-live-status__steps" aria-hidden="true">
        {status.steps.map((step) => (
          <div key={step} className="orchestrator-live-status__step">
            <div className="orchestrator-live-status__skeleton" />
            <span>{step}</span>
          </div>
        ))}
      </div>

      {status.facts?.length ? (
        <dl className="orchestrator-live-status__facts">
          {status.facts.map((fact) => (
            <div key={`${fact.label}-${fact.value}`} className="orchestrator-live-status__fact">
              <dt>{fact.label}</dt>
              <dd>{fact.value}</dd>
              {fact.action ? (
                <button
                  type="button"
                  className="chat-page__action-btn orchestrator-live-status__fact-action"
                  disabled={isSending || pendingActionMessage !== null}
                  onClick={() => void handleFactAction(fact.action!.message)}
                >
                  {pendingActionMessage === fact.action.message
                    ? (fact.action.pending_label ?? "发送中...")
                    : fact.action.label}
                </button>
              ) : null}
            </div>
          ))}
        </dl>
      ) : null}
    </section>
  );
}

type LiveStatusDescriptor = {
  label: string;
  title: string;
  detail: string;
  badge?: string;
  tone: "dispatching" | "verifying" | "queued";
  steps: string[];
  facts?: Array<{
    label: string;
    value: string;
    action?: {
      label: string;
      message: string;
      pending_label?: string;
    };
  }>;
  action?: {
    label: string;
    sessionId: string;
    pending_label?: string;
  };
};

function resolveLiveStatus(session: OrchestratorSession): LiveStatusDescriptor | null {
  const coordination = session.coordination;
  const resumeTarget = resolveResumeTarget(session);
  const resumeAction = resolveResumeAction(session);

  if (coordination?.mode === "preempted") {
    return {
      label: "Session Pool",
      title: "当前会话暂未占用执行槽位",
      detail: coordination.waiting_reason || "当前会话被更高优先级项目抢占，正在等待重新获得执行权。",
      badge: coordination.queue_position ? `队列位置 #${coordination.queue_position}` : undefined,
      tone: "queued",
      steps: ["保留当前计划上下文", "等待执行槽位释放", "恢复本会话派发顺序"],
      facts: [
        {
          label: "预计等待原因",
          value: coordination.waiting_reason || "当前会话被更高优先级项目抢占，等待重新获得执行权。",
        },
        {
          label: "恢复后优先执行",
          value: resumeTarget,
          action: resumeAction,
        },
      ],
      action: coordination.preempted_by_session_id
        ? {
            label: "查看抢占会话",
            sessionId: coordination.preempted_by_session_id,
            pending_label: "切换中...",
          }
        : undefined,
    };
  }

  if (coordination?.mode === "queued") {
    return {
      label: "Session Pool",
      title: "当前会话正在队列中等待",
      detail: coordination.waiting_reason || "执行槽位暂时不足，当前会话正在排队。",
      badge: coordination.queue_position ? `队列位置 #${coordination.queue_position}` : undefined,
      tone: "queued",
      steps: ["等待可用并行槽位", "保留已审批计划边界", "轮到后自动继续派发"],
      facts: [
        {
          label: "预计等待原因",
          value: coordination.waiting_reason || "当前并行槽位已满，正在等待其他项目释放执行资源。",
        },
        {
          label: "恢复后优先执行",
          value: resumeTarget,
          action: resumeAction,
        },
      ],
    };
  }

  if (session.status === "dispatching") {
    return {
      label: "Dispatch",
      title: "正在派发任务",
      detail: coordination?.waiting_reason || session.summary || "正在把本轮可执行任务分配给 delegate。",
      badge: coordination?.dispatch_slot ? `槽位 #${coordination.dispatch_slot}` : undefined,
      tone: "dispatching",
      steps: ["整理本轮可执行任务", "校对 scope 与验收边界", "等待 Codex delegate 接管"],
    };
  }

  if (session.status === "verifying" || coordination?.mode === "verifying") {
    return {
      label: "Verification",
      title: "正在统一验收",
      detail: coordination?.waiting_reason || session.summary || "统一验收已开始，正在执行计划内命令。",
      badge: coordination?.dispatch_slot ? `槽位 #${coordination.dispatch_slot}` : undefined,
      tone: "verifying",
      steps: ["执行计划内验收命令", "汇总 command 结果", "准备最终摘要"],
    };
  }

  return null;
}

function resolveResumeTarget(session: OrchestratorSession): string {
  const resumeTask = resolveResumeTask(session);
  if (resumeTask) {
    return `${resumeTask.kind.toUpperCase()} · ${resumeTask.title}`;
  }

  if (session.status === "pending_plan_approval") {
    return "回到计划审批";
  }

  return session.summary || "等待新的主控指令";
}

function resolveResumeAction(
  session: OrchestratorSession,
): {
  label: string;
  message: string;
} | undefined {
  const resumeTask = resolveResumeTask(session);
  if (!resumeTask) {
    return undefined;
  }

  return {
    label: "继续推进这个任务",
    message: `继续推进任务「${resumeTask.title}」，并告诉我你准备怎么做`,
    pending_label: "推进中...",
  };
}

function resolveResumeTask(session: OrchestratorSession) {
  const runningTask = session.plan?.tasks.find((task) => task.status === "running");
  if (runningTask) {
    return runningTask;
  }

  const nextTask = session.plan?.tasks.find((task) => task.status === "pending" || task.status === "queued");
  if (nextTask) {
    return nextTask;
  }

  return undefined;
}
