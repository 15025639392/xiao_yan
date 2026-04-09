import { useMemo, useState } from "react";

import { OrchestratorConversationPanel } from "../components/orchestrator/OrchestratorConversationPanel";
import type { OrchestratorMessage, OrchestratorSchedulerSnapshot, OrchestratorSession } from "../lib/api";
import { getProjectNameFromPath } from "../lib/projects";

export type OrchestratorPageProps = {
  sessions: OrchestratorSession[];
  scheduler: OrchestratorSchedulerSnapshot;
  messages: OrchestratorMessage[];
  activeSessionId: string | null;
  activeProjectPath: string | null;
  draft: string;
  isSending: boolean;
  onDraftChange: (value: string) => void;
  onSendMessage: () => Promise<void> | void;
  onActivateSession: (sessionId: string) => Promise<void>;
  onApprovePlan: (sessionId: string) => Promise<void>;
  onRejectPlan: (sessionId: string) => Promise<void>;
  onResumeSession: (sessionId: string) => Promise<void>;
  onSubmitDirective: (sessionId: string, message: string) => Promise<void>;
  onCancelSession: (sessionId: string) => Promise<void>;
  onSendQuickMessage: (message: string) => Promise<void> | void;
};

type SidebarTab = "plan" | "tasks" | "verification" | "sessions";

export function OrchestratorPage({
  sessions,
  scheduler,
  messages,
  activeSessionId,
  activeProjectPath,
  draft,
  isSending,
  onDraftChange,
  onSendMessage,
  onActivateSession,
  onApprovePlan,
  onRejectPlan,
  onResumeSession,
  onCancelSession,
  onSendQuickMessage,
}: OrchestratorPageProps) {
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [activeTab, setActiveTab] = useState<SidebarTab>("plan");
  const session = sessions.find((item) => item.session_id === activeSessionId) ?? sessions[0] ?? null;

  const metrics = useMemo(() => {
    const tasks = session?.plan?.tasks ?? [];
    return {
      total: tasks.length,
      done: tasks.filter((task) => task.status === "succeeded").length,
      running: tasks.filter((task) => task.status === "running").length,
      failed: tasks.filter((task) => task.status === "failed").length,
    };
  }, [session]);

  if (!session) {
    return (
      <section className="orchestrator-page orchestrator-page--empty">
        <div className="orchestrator-empty-card">
          <div className="orchestrator-empty-card__badge">主控工作台</div>
          <h2 className="orchestrator-empty-card__title">等待显式进入主控模式</h2>
          <p className="orchestrator-empty-card__desc">
            在聊天里发送“进入主控，处理当前项目”后，小晏会切到这里，用对话方式持续推进当前项目。
          </p>
          <div className="orchestrator-empty-card__meta">
            <span>当前主控项目</span>
            <strong>{activeProjectPath ? getProjectNameFromPath(activeProjectPath) : "未选择项目"}</strong>
          </div>
        </div>
      </section>
    );
  }

  return (
    <section className="orchestrator-page orchestrator-page--chatfirst">
      <header className="orchestrator-chat-header">
        <div className="orchestrator-chat-header__copy">
          <p className="orchestrator-page__eyebrow">Orchestrator V3</p>
          <h2 className="orchestrator-page__title">{session.project_name}</h2>
          <p className="orchestrator-page__subtitle">{session.goal}</p>
        </div>
        <div className="orchestrator-chat-header__meta">
          <span className={`orchestrator-status orchestrator-status--${session.status}`}>{renderSessionStatus(session.status)}</span>
          <span className="orchestrator-pill">{metrics.done}/{metrics.total || 0} 已完成</span>
          {session.coordination?.queue_position ? <span className="orchestrator-pill">队列 #{session.coordination.queue_position}</span> : null}
          <span className="orchestrator-pill">并行上限 {scheduler.max_parallel_sessions}</span>
        </div>
        <div className="orchestrator-page__header-actions">
          {session.status === "pending_plan_approval" ? (
            <button className="btn btn--primary btn--sm" onClick={() => void onApprovePlan(session.session_id)} type="button">
              批准并开工
            </button>
          ) : null}
          {session.status !== "pending_plan_approval" && canResumeSession(session) ? (
            <button className="btn btn--secondary btn--sm" onClick={() => void onResumeSession(session.session_id)} type="button">
              {session.coordination?.failure_category === "verification_failure" ? "重跑验收" : "恢复推进"}
            </button>
          ) : null}
          <button className="btn btn--ghost btn--sm" onClick={() => void setAdvancedOpen((value) => !value)} type="button">
            {advancedOpen ? "收起高级信息" : "展开高级信息"}
          </button>
          <button className="btn btn--ghost btn--sm" onClick={() => void onCancelSession(session.session_id)} type="button">
            退出主控
          </button>
        </div>
      </header>

      <div className={`orchestrator-chat-layout ${advancedOpen ? "orchestrator-chat-layout--sidebar-open" : ""}`}>
        <div className="orchestrator-chat-main">
          <OrchestratorConversationPanel
            session={session}
            messages={messages}
            draft={draft}
            isSending={isSending}
            onDraftChange={onDraftChange}
            onSendMessage={() => void onSendMessage()}
            onApprovePlan={onApprovePlan}
            onRejectPlan={onRejectPlan}
            onResumeSession={onResumeSession}
            onCancelSession={onCancelSession}
            onActivateSession={onActivateSession}
            onSendQuickMessage={onSendQuickMessage}
          />

          {advancedOpen ? (
            <section className="orchestrator-chat-advanced" aria-label="主控高级信息">
              <div className="orchestrator-chat-context-bar">
                <div className="orchestrator-chat-context-item">
                  <span>当前焦点</span>
                  <strong>{resolveCurrentFocus(session)}</strong>
                </div>
                <div className="orchestrator-chat-context-item">
                  <span>下一步</span>
                  <strong>{resolveNextMove(session)}</strong>
                </div>
                <div className="orchestrator-chat-context-item">
                  <span>等待原因</span>
                  <strong>{session.coordination?.waiting_reason || "主控已就绪"}</strong>
                </div>
              </div>

              {session.status === "pending_plan_approval" ? (
                <div className="orchestrator-chat-advanced__actions">
                  <button className="btn btn--secondary btn--sm" onClick={() => void onRejectPlan(session.session_id)} type="button">
                    拒绝计划
                  </button>
                </div>
              ) : null}
            </section>
          ) : null}
        </div>

        {advancedOpen ? (
          <aside className="orchestrator-chat-sidebar">
            <div className="orchestrator-chat-sidebar__tabs" role="tablist" aria-label="主控侧栏">
              {[
                ["plan", "计划"],
                ["tasks", "任务"],
                ["verification", "验收"],
                ["sessions", "会话池"],
              ].map(([key, label]) => (
                <button
                  key={key}
                  type="button"
                  role="tab"
                  className={`orchestrator-chat-sidebar__tab ${activeTab === key ? "orchestrator-chat-sidebar__tab--active" : ""}`}
                  aria-selected={activeTab === key}
                  onClick={() => setActiveTab(key as SidebarTab)}
                >
                  {label}
                </button>
              ))}
            </div>

            <div className="orchestrator-chat-sidebar__panel">
              {activeTab === "plan" ? <PlanSidebar session={session} /> : null}
              {activeTab === "tasks" ? <TasksSidebar session={session} /> : null}
              {activeTab === "verification" ? <VerificationSidebar session={session} /> : null}
              {activeTab === "sessions" ? (
                <SessionsSidebar sessions={sessions} activeSessionId={session.session_id} onActivateSession={onActivateSession} />
              ) : null}
            </div>
          </aside>
        ) : null}
      </div>
    </section>
  );
}

function PlanSidebar({ session }: { session: OrchestratorSession }) {
  if (!session.plan) {
    return <p className="orchestrator-empty">主控计划还没生成。</p>;
  }

  return (
    <div className="orchestrator-side-section">
      <span className="orchestrator-side-section__label">Definition of done</span>
      <ul className="orchestrator-side-list">
        {session.plan.definition_of_done.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
      <span className="orchestrator-side-section__label">项目快照</span>
      <dl className="orchestrator-snapshot-list orchestrator-snapshot-list--stacked">
        <div>
          <dt>路径</dt>
          <dd>{session.plan.project_snapshot.project_path}</dd>
        </div>
        <div>
          <dt>语言</dt>
          <dd>{session.plan.project_snapshot.languages.join(" / ") || "未知"}</dd>
        </div>
        <div>
          <dt>入口</dt>
          <dd>{session.plan.project_snapshot.entry_files.join(" · ") || "未识别"}</dd>
        </div>
      </dl>
    </div>
  );
}

function TasksSidebar({ session }: { session: OrchestratorSession }) {
  const tasks = session.plan?.tasks ?? [];
  if (tasks.length === 0) {
    return <p className="orchestrator-empty">还没有任务。</p>;
  }

  return (
    <ol className="orchestrator-flow-list">
      {tasks.map((task) => (
        <li key={task.task_id} className={`orchestrator-flow-step orchestrator-flow-step--${task.status}`}>
          <div className="orchestrator-flow-step__marker" />
          <div className="orchestrator-flow-step__body">
            <div className="orchestrator-flow-step__head">
              <div>
                <div className="orchestrator-flow-step__eyebrow">{task.kind.toUpperCase()}</div>
                <strong>{task.title}</strong>
              </div>
              <span className={`orchestrator-pill orchestrator-pill--${task.status}`}>{renderTaskStatus(task.status)}</span>
            </div>
            <p className="orchestrator-flow-step__summary">{task.result_summary || task.error || "等待推进"}</p>
          </div>
        </li>
      ))}
    </ol>
  );
}

function VerificationSidebar({ session }: { session: OrchestratorSession }) {
  if (!session.verification) {
    return <p className="orchestrator-empty">统一验收尚未开始。</p>;
  }

  return (
    <div className="orchestrator-side-section">
      <span className="orchestrator-side-section__label">验收结果</span>
      <p className="orchestrator-verification__summary">{session.verification.summary || "暂无摘要"}</p>
      <ul className="orchestrator-command-list">
        {session.verification.commands.map((command) => (
          <li key={command}>
            <code>{command}</code>
          </li>
        ))}
      </ul>
    </div>
  );
}

function SessionsSidebar({
  sessions,
  activeSessionId,
  onActivateSession,
}: {
  sessions: OrchestratorSession[];
  activeSessionId: string;
  onActivateSession: (sessionId: string) => Promise<void>;
}) {
  return (
    <ul className="orchestrator-session-list">
      {sessions.map((item) => (
        <li key={item.session_id}>
          <button
            type="button"
            className={`orchestrator-session-card ${item.session_id === activeSessionId ? "orchestrator-session-card--active" : ""}`}
            onClick={() => void onActivateSession(item.session_id)}
          >
            <div className="orchestrator-session-card__top">
              <strong>{item.project_name}</strong>
              <span className={`orchestrator-pill orchestrator-pill--${item.status}`}>{renderSessionStatus(item.status)}</span>
            </div>
            <p>{item.goal}</p>
            <div className="orchestrator-session-card__meta">
              <span>{new Date(item.updated_at).toLocaleString()}</span>
            </div>
          </button>
        </li>
      ))}
    </ul>
  );
}

function canResumeSession(session: OrchestratorSession): boolean {
  return session.status === "failed" || session.status === "cancelled";
}

function resolveCurrentFocus(session: OrchestratorSession): string {
  const runningTask = session.plan?.tasks.find((task) => task.status === "running");
  if (runningTask) {
    return `${runningTask.kind.toUpperCase()} · ${runningTask.title}`;
  }
  if (session.status === "pending_plan_approval") {
    return "等待计划审批";
  }
  return session.summary || "等待下一步";
}

function resolveNextMove(session: OrchestratorSession): string {
  const nextTask = session.plan?.tasks.find((task) => task.status === "pending" || task.status === "queued");
  if (nextTask) {
    return `${nextTask.kind.toUpperCase()} · ${nextTask.title}`;
  }
  if (session.status === "completed") {
    return "查看最终摘要与验收结果";
  }
  if (session.status === "failed") {
    return "恢复失败环节或调整边界后重试";
  }
  return "等待新指令";
}

function renderSessionStatus(status: OrchestratorSession["status"]): string {
  if (status === "pending_plan_approval") return "待审批";
  if (status === "dispatching") return "待派发";
  if (status === "running") return "运行中";
  if (status === "verifying") return "验收中";
  if (status === "completed") return "已完成";
  if (status === "failed") return "失败";
  if (status === "cancelled") return "已取消";
  if (status === "planning") return "规划中";
  return "草稿";
}

function renderTaskStatus(status: NonNullable<OrchestratorSession["plan"]>["tasks"][number]["status"]): string {
  if (status === "pending") return "待执行";
  if (status === "queued") return "排队中";
  if (status === "running") return "运行中";
  if (status === "succeeded") return "已完成";
  if (status === "failed") return "失败";
  return "已取消";
}
