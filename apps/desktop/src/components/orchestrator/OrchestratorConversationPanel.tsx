import { useEffect, useRef, type KeyboardEvent as ReactKeyboardEvent } from "react";

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
  onToggleSidebar,
  sidebarOpen,
}: OrchestratorConversationPanelProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const messagesContainerRef = useRef<HTMLDivElement>(null);
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
      <div ref={messagesContainerRef} className="chat-page__messages orchestrator-chat-shell__messages">
        <div className="orchestrator-chat-context">
          <div className="orchestrator-chat-context__meta">
            <span className="orchestrator-chat-context__label">当前会话</span>
            <span className="orchestrator-chat-context__name">{session.project_name}</span>
          </div>

          <button
            className="orchestrator-chat-context__toggle"
            onClick={onToggleSidebar}
            type="button"
            title={sidebarOpen ? "收起高级信息" : "展开高级信息"}
            aria-label={sidebarOpen ? "收起高级信息" : "展开高级信息"}
          >
            {sidebarOpen ? "收起侧栏" : "展开侧栏"}
          </button>
        </div>
        {messages.length === 0 ? (
          <div className="chat-page__empty">
            <p className="chat-page__empty-desc">直接输入任务指令即可，先看全局进度也可以。</p>
            <button
              className="orchestrator-quick-action"
              onClick={() => void onSendQuickMessage("先解释当前推进到哪一步")}
              type="button"
            >
              查看进度
            </button>
          </div>
        ) : (
          <>
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
              placeholder="输入指令：例如“拆分任务并分配给工程师1号和2号”"
              onChange={(event) => onDraftChange(event.target.value)}
              onKeyDown={handleKeyDown}
              rows={1}
              disabled={isSending}
            />
            <button className="chat-page__send-btn" type="submit" disabled={isSending || !draft.trim()} aria-label="发送主控消息">
              {isSending ? "..." : "↑"}
            </button>
          </div>
        </form>
      </div>
    </section>
  );
}
