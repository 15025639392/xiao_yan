import { useMemo, useState } from "react";

import { OrchestratorConversationPanel } from "../components/orchestrator/OrchestratorConversationPanel";
import { ExecutorPanel } from "../components/orchestrator/ExecutorPanel";
import { SessionHistoryPanel } from "../components/orchestrator/SessionHistoryPanel";
import { TaskBoardPanel } from "../components/orchestrator/TaskBoardPanel";
import { Button } from "../components/ui";
import type { OrchestratorMessage, OrchestratorSchedulerSnapshot, OrchestratorSession, WorkbenchTab } from "../lib/api";
import {
  buildWorkbenchViewModel,
  type SessionHistoryFilter,
} from "../lib/orchestratorWorkbench";
import type { ImportedProjectRegistry } from "../lib/projects";
import { getProjectNameFromPath } from "../lib/projects";

export type StopDelegateTaskRequest = {
  sessionId: string;
  taskId: string;
  runId: string;
};

export type OrchestratorPageProps = {
  sessions: OrchestratorSession[];
  historySessions: OrchestratorSession[];
  workbenchTabs: WorkbenchTab[];
  activeWorkbenchTabId: string | null;
  scheduler: OrchestratorSchedulerSnapshot;
  messages: OrchestratorMessage[];
  activeSessionId: string | null;
  activeProjectPath: string | null;
  draft: string;
  isSending: boolean;
  historyFilter: SessionHistoryFilter;
  onHistoryFilterChange: (next: SessionHistoryFilter) => void;
  onApplyHistoryFilter: (next: SessionHistoryFilter) => Promise<void> | void;
  onActivateWorkbenchTab: (tabId: string) => void;
  onCloseWorkbenchTab: (tabId: string) => void;
  onCreateBlankTab: () => void;
  onDraftChange: (value: string) => void;
  onSendMessage: () => Promise<void> | void;
  onActivateSession: (sessionId: string) => Promise<void>;
  onApprovePlan: (sessionId: string) => Promise<void>;
  onRejectPlan: (sessionId: string) => Promise<void>;
  onResumeSession: (sessionId: string) => Promise<void>;
  onCancelSession: (sessionId: string) => Promise<void>;
  onCreateSession: (goal: string) => Promise<void> | void;
  onDeleteSession: (sessionId: string) => Promise<void> | void;
  onSendQuickMessage: (message: string) => Promise<void> | void;
  onStopDelegateTask: (payload: StopDelegateTaskRequest) => Promise<void> | void;
  projectRegistry: ImportedProjectRegistry;
  isUpdatingProjects: boolean;
  projectError: string;
  tauriSupported: boolean;
  onImportProject: () => Promise<void>;
  onActivateProject: (path: string) => Promise<void>;
  onRemoveProject: (path: string) => Promise<void>;
};

type SidebarFocus = "task_board" | "executors" | "session_history";

export function OrchestratorPage({
  sessions,
  historySessions,
  workbenchTabs,
  activeWorkbenchTabId,
  scheduler,
  messages,
  activeSessionId,
  activeProjectPath,
  draft,
  isSending,
  historyFilter,
  onHistoryFilterChange,
  onApplyHistoryFilter,
  onActivateWorkbenchTab,
  onCloseWorkbenchTab,
  onCreateBlankTab,
  onDraftChange,
  onSendMessage,
  onActivateSession,
  onApprovePlan,
  onRejectPlan,
  onResumeSession,
  onCancelSession,
  onCreateSession,
  onDeleteSession,
  onSendQuickMessage,
  onStopDelegateTask,
  projectRegistry,
  isUpdatingProjects,
  projectError,
  tauriSupported,
  onImportProject,
  onActivateProject,
  onRemoveProject,
}: OrchestratorPageProps) {
  const [sidePanelOpen, setSidePanelOpen] = useState(false);
  const activeWorkbenchTab =
    workbenchTabs.find((item) => item.tab_id === activeWorkbenchTabId) ?? workbenchTabs[0] ?? null;
  const session =
    activeWorkbenchTab?.type === "session"
      ? sessions.find((item) => item.session_id === activeWorkbenchTab.session_id) ?? null
      : null;
  const displaySession = session ?? buildBlankDisplaySession(activeWorkbenchTab, activeProjectPath);

  const workbench = useMemo(
    () =>
      buildWorkbenchViewModel({
        sessions: session ? sessions : [],
        activeSessionId: session ? session.session_id : null,
        scheduler,
        historySessions,
      }),
    [session, sessions, scheduler, historySessions],
  );
  const sidebarFocus = useMemo(() => resolveSidebarFocus(workbench), [workbench]);

  if (!activeWorkbenchTab) {
    return (
      <section className="orchestrator-page orchestrator-page--empty">
        <div className="orchestrator-empty-card">
          <div className="orchestrator-empty-card__badge">主控工作台</div>
          <h2 className="orchestrator-empty-card__title">主控工作台待命中</h2>
          <p className="orchestrator-empty-card__desc">
            这里用于持续推进当前项目；当存在主控会话时，会展示对应的工作台内容。
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
    <div className={`orchestrator-chat-layout ${sidePanelOpen ? "orchestrator-chat-layout--sidebar-open" : ""}`}>
      <div className="orchestrator-chat-main">
        <section className="orchestrator-workbench-tabs" aria-label="主控会话页签">
          <div className="orchestrator-workbench-tabs__scroll">
            {workbenchTabs.map((tab) => {
              const isActive = tab.tab_id === activeWorkbenchTab.tab_id;
              const label = tab.type === "session"
                ? resolveSessionTabLabel(sessions, tab.session_id)
                : "空白会话";
              return (
                <div
                  key={tab.tab_id}
                  className={`orchestrator-workbench-tab ${isActive ? "orchestrator-workbench-tab--active" : ""}`}
                >
                  <Button
                    type="button"
                    variant="ghost"
                    className="orchestrator-workbench-tab__label"
                    onClick={() => onActivateWorkbenchTab(tab.tab_id)}
                  >
                    {label}
                  </Button>
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    className="orchestrator-workbench-tab__close"
                    onClick={() => onCloseWorkbenchTab(tab.tab_id)}
                    aria-label={`关闭${label}`}
                  >
                    ×
                  </Button>
                </div>
              );
            })}
          </div>
          <Button
            type="button"
            variant="secondary"
            className="orchestrator-workbench-tab__add"
            onClick={onCreateBlankTab}
            aria-label="新建空白会话"
          >
            + 新建会话
          </Button>
        </section>

        <OrchestratorConversationPanel
          session={displaySession}
          messages={session ? messages : []}
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
          onToggleSidebar={() => setSidePanelOpen((current) => !current)}
          sidebarOpen={sidePanelOpen}
        />
      </div>

      {sidePanelOpen ? (
        <aside className="orchestrator-chat-sidebar">
          <div className="orchestrator-chat-sidebar__focus" aria-live="polite">
            <span className="orchestrator-chat-sidebar__focus-label">当前最需要关注</span>
            <strong className="orchestrator-chat-sidebar__focus-title">{sidebarFocus.title}</strong>
            <span className="orchestrator-chat-sidebar__focus-reason">{sidebarFocus.reason}</span>
          </div>

          <div className="orchestrator-chat-sidebar__panel">
            {sidebarFocus.focus === "task_board" ? (
              <TaskBoardPanel
                viewModel={workbench.taskBoard}
                onSendQuickMessage={onSendQuickMessage}
              />
            ) : null}
            {sidebarFocus.focus === "executors" ? (
              <ExecutorPanel
                executors={workbench.executors}
                onSendQuickMessage={onSendQuickMessage}
                onStopTask={onStopDelegateTask}
              />
            ) : null}
            {sidebarFocus.focus === "session_history" ? (
              <SessionHistoryPanel
                viewModel={workbench.sessionHub}
                filter={historyFilter}
                activeSessionId={session?.session_id ?? null}
                onFilterChange={onHistoryFilterChange}
                onApplyFilter={onApplyHistoryFilter}
                onActivateSession={onActivateSession}
                onResumeSession={onResumeSession}
                onDeleteSession={onDeleteSession}
              />
            ) : null}
          </div>
        </aside>
      ) : null}
    </div>
  );
}

function resolveSidebarFocus(workbench: ReturnType<typeof buildWorkbenchViewModel>): {
  focus: SidebarFocus;
  title: string;
  reason: string;
} {
  const stalledExecutors = workbench.executors.filter((executor) => executor.stalled).length;
  const runningExecutors = workbench.executors.filter((executor) => executor.status === "running").length;

  if (stalledExecutors > 0 || runningExecutors > 0) {
    const reason =
      stalledExecutors > 0
        ? `有 ${stalledExecutors} 个执行者出现卡点，需要主控立即介入`
        : `有 ${runningExecutors} 个执行者正在运行，优先盯执行回执`;
    return {
      focus: "executors",
      title: "执行者",
      reason,
    };
  }

  const actionableTasks = workbench.taskBoard.tasks.filter((task) =>
    ["pending", "queued", "running", "failed"].includes(task.status),
  ).length;
  if (actionableTasks > 0) {
    return {
      focus: "task_board",
      title: "任务编排",
      reason: `当前有 ${actionableTasks} 个任务待推进或待修复`,
    };
  }

  return {
    focus: "session_history",
    title: "会话历史",
    reason: "当前会话已相对稳定，建议查看历史会话并按需恢复",
  };
}

function resolveSessionTabLabel(sessions: OrchestratorSession[], sessionId: string): string {
  const session = sessions.find((item) => item.session_id === sessionId);
  if (!session) {
    return `会话 ${sessionId.slice(0, 6)}`;
  }
  return session.project_name || `会话 ${sessionId.slice(0, 6)}`;
}

function buildBlankDisplaySession(tab: WorkbenchTab | null, activeProjectPath: string | null): OrchestratorSession {
  const projectName = activeProjectPath ? getProjectNameFromPath(activeProjectPath) : "未选择项目";
  return {
    session_id: tab?.tab_id ?? "blank-tab",
    project_path: activeProjectPath ?? "",
    project_name: projectName,
    goal: "等待第一条指令",
    status: "draft",
    plan: null,
    delegates: [],
    coordination: {
      mode: "idle",
      priority_score: 0,
      waiting_reason: "空白会话待命中，发送第一条指令后自动创建主控会话。",
    },
    verification: null,
    summary: "空白会话待命中",
    entered_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  };
}
