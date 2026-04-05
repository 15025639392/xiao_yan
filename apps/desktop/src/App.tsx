import { useEffect, useState } from "react";

import { AutobioPanel } from "./components/AutobioPanel";
import { ChatPanel } from "./components/ChatPanel";
import type { ChatEntry } from "./components/ChatPanel";
import { GoalsPanel } from "./components/GoalsPanel";
import { HistoryPanel } from "./components/HistoryPanel";
import type { SelfImprovementHistoryEntry } from "./lib/api";
import { SettingsPanel } from "./components/SettingsPanel";
import { StatusPanel } from "./components/StatusPanel";
import { ToolPanel } from "./components/ToolPanel";
import { WorldPanel } from "./components/WorldPanel";
import type { BeingState, ChatHistoryMessage, Goal, InnerWorldState } from "./lib/api";
import {
  chat,
  fetchGoals,
  fetchAutobio,
  fetchMessages,
  fetchState,
  fetchWorld,
  sleep,
  updateGoalStatus,
  wake,
} from "./lib/api";

type AppRoute = "overview" | "chat" | "settings" | "history" | "tools";

const initialState: BeingState = {
  mode: "sleeping",
  focus_mode: "sleeping",
  current_thought: null,
  active_goal_ids: [],
  today_plan: null,
  last_action: null,
  self_improvement_job: null,
};

export default function App() {
  const [route, setRoute] = useState<AppRoute>(() => resolveRoute(window.location.hash));
  const [state, setState] = useState<BeingState>(initialState);
  const [world, setWorld] = useState<InnerWorldState | null>(null);
  const [autobioEntries, setAutobioEntries] = useState<string[]>([]);
  const [messages, setMessages] = useState<ChatEntry[]>([]);
  const [goals, setGoals] = useState<Goal[]>([]);
  const [draft, setDraft] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState("");
  const [theme, setTheme] = useState<"dark" | "light">(() => loadThemePreference());
  const [showHistory, setShowHistory] = useState(false);
  const focusGoalTitle = resolveFocusGoalTitle(state, goals);

  useEffect(() => {
    let cancelled = false;

    async function syncRuntime() {
      try {
        const [nextState, nextMessages, nextGoals, nextWorld, nextAutobio] = await Promise.all([
          fetchState(),
          fetchMessages(),
          fetchGoals(),
          fetchWorld(),
          fetchAutobio(),
        ]);

        if (cancelled) {
          return;
        }

        setState(nextState);
        setMessages((current) => mergeMessages(current, nextMessages.messages));
        setGoals(nextGoals.goals);
        setWorld(nextWorld);
        setAutobioEntries(nextAutobio.entries);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "同步失败");
        }
      }
    }

    void syncRuntime();
    const timer = window.setInterval(() => {
      void syncRuntime();
    }, 5000);

    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, []);

  // 主题切换：更新 DOM 和 localStorage
  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("theme", theme);
  }, [theme]);

  useEffect(() => {
    const syncRoute = () => {
      setRoute(resolveRoute(window.location.hash));
    };

    if (!window.location.hash) {
      window.location.hash = routeToHash("overview");
    } else {
      syncRoute();
    }

    window.addEventListener("hashchange", syncRoute);
    return () => {
      window.removeEventListener("hashchange", syncRoute);
    };
  }, []);

  async function handleWake() {
    try {
      setError("");
      setState(await wake());
    } catch (err) {
      setError(err instanceof Error ? err.message : "唤醒失败");
    }
  }

  async function handleSleep() {
    try {
      setError("");
      setState(await sleep());
    } catch (err) {
      setError(err instanceof Error ? err.message : "休眠失败");
    }
  }

  async function handleSend() {
    const content = draft.trim();
    if (!content) {
      return;
    }

    const userMessage: ChatEntry = {
      id: `user-${Date.now()}`,
      role: "user",
      content,
    };

    setError("");
    setDraft("");
    setMessages((current) => [...current, userMessage]);
    setIsSending(true);

    try {
      const result = await chat(content);
      setMessages((current) => [
        ...current,
        {
          id: result.response_id ?? `assistant-${Date.now()}`,
          role: "assistant",
          content: result.output_text,
        },
      ]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "发送失败");
    } finally {
      setIsSending(false);
    }
  }

  async function handleUpdateGoalStatus(goalId: string, status: Goal["status"]) {
    try {
      setError("");
      const updatedGoal = await updateGoalStatus(goalId, status);
      const refreshedState = await fetchState();

      setGoals((current) =>
        current.map((goal) => (goal.id === updatedGoal.id ? updatedGoal : goal))
      );
      setState(refreshedState);
    } catch (err) {
      setError(err instanceof Error ? err.message : "目标状态更新失败");
    }
  }

  async function handleRollback(jobId: string) {
    try {
      setError("");
      // 回滚后刷新状态
      const refreshedState = await fetchState();
      setState(refreshedState);
    } catch (err) {
      setError(err instanceof Error ? err.message : "回滚失败");
    }
  }

  async function handleApprovalDecision(jobId: string, approved: boolean) {
    try {
      setError("");
      // 审批操作已由 ApprovalPanel 内部调用 API 完成，这里只做状态刷新
      const refreshedState = await fetchState();
      setState(refreshedState);
    } catch (err) {
      setError(err instanceof Error ? err.message : "审批状态更新失败");
    }
  }

  function handleNavigate(nextRoute: AppRoute) {
    const nextHash = routeToHash(nextRoute);
    if (window.location.hash !== nextHash) {
      window.location.hash = nextHash;
      return;
    }

    setRoute(nextRoute);
  }

  const isAwake = state.mode === "awake";

  return (
    <div className="app-layout">
      {/* Left Sidebar - WorkBuddy Style */}
      <aside className="app-sidebar">
        <div className="app-sidebar__header">
          <button
            className="app-sidebar__brand"
            onClick={() => handleNavigate("settings")}
            type="button"
            title="设置"
          >
            <span className="app-sidebar__logo">🤖</span>
            <span className="app-sidebar__title">数字人</span>
          </button>
          <div className={`app-sidebar__status-dot app-sidebar__status-dot--${state.mode}`} />
        </div>

        <nav className="app-sidebar__nav" aria-label="主导航">
          <button
            className={`app-sidebar__nav-item ${route === "overview" ? "app-sidebar__nav-item--active" : ""}`}
            onClick={() => handleNavigate("overview")}
            type="button"
          >
            <svg className="app-sidebar__nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <rect x="3" y="3" width="7" height="7" rx="1" />
              <rect x="14" y="3" width="7" height="7" rx="1" />
              <rect x="14" y="14" width="7" height="7" rx="1" />
              <rect x="3" y="14" width="7" height="7" rx="1" />
            </svg>
            <span>总览</span>
          </button>
          <button
            className={`app-sidebar__nav-item ${route === "chat" ? "app-sidebar__nav-item--active" : ""}`}
            onClick={() => handleNavigate("chat")}
            type="button"
          >
            <svg className="app-sidebar__nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
            </svg>
            <span>对话</span>
          </button>
          <button
            className={`app-sidebar__nav-item ${route === "history" ? "app-sidebar__nav-item--active" : ""}`}
            onClick={() => handleNavigate("history")}
            type="button"
          >
            <svg className="app-sidebar__nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>
            </svg>
            <span>历史</span>
          </button>
          <button
            className={`app-sidebar__nav-item ${route === "tools" ? "app-sidebar__nav-item--active" : ""}`}
            onClick={() => handleNavigate("tools")}
            type="button"
          >
            <svg className="app-sidebar__nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M14.7 6.3a1 1 0 0 0 0-1.4l1.83-2a1 1 0 0 0-1.42-1.4L13.28 5.17a4 4 0 1 0-5.66 5.66l-8.49 8.49a1 1 0 0 0-1.41 0"/>
              <path d="M16 21v-6a1 1 0 0 1 1-1h6"/>
            </svg>
            <span>工具箱</span>
          </button>
        </nav>

        <div className="app-sidebar__section">
          <div className="app-sidebar__section-title">控制</div>
          <div className="app-sidebar__actions">
            <button
              className="app-sidebar__action-btn app-sidebar__action-btn--primary"
              onClick={handleWake}
              type="button"
              disabled={isAwake}
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83" />
              </svg>
              唤醒
            </button>
            <button
              className="app-sidebar__action-btn"
              onClick={handleSleep}
              type="button"
              disabled={!isAwake}
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
              </svg>
              休眠
            </button>
          </div>
        </div>

        <div className="app-sidebar__footer">
          <div className="app-sidebar__status">
            <span className={`app-sidebar__status-indicator app-sidebar__status-indicator--${state.mode}`} />
            <span className="app-sidebar__status-text">{isAwake ? "运行中" : "休眠中"}</span>
          </div>
        </div>
      </aside>

      {/* Main Content */}
      <main className="app-main">
        {/* Error Banner */}
        {error ? (
          <div className="error-banner">
            <strong>错误：</strong>
            {error}
          </div>
        ) : null}

        {route === "chat" ? (
          <ChatPanel
            draft={draft}
            focusGoalTitle={focusGoalTitle}
            focusModeLabel={renderFocusModeLabel(state.focus_mode)}
            isSending={isSending}
            messages={messages}
            modeLabel={isAwake ? "运行中" : "休眠中"}
            todayPlan={state.today_plan}
            activeGoals={goals.filter(g => g.status === "active")}
            onDraftChange={setDraft}
            onSend={handleSend}
            onCompleteGoal={(goalId) => handleUpdateGoalStatus(goalId, "completed")}
          />
        ) : route === "settings" ? (
          <SettingsPanel theme={theme} onThemeChange={setTheme} />
        ) : route === "history" ? (
          <HistoryPage onSelectRollback={handleRollback} />
        ) : route === "tools" ? (
          <ToolPanel />
        ) : (
          <OverviewPanel
            focusGoalTitle={focusGoalTitle}
            goals={goals}
            latestActionLabel={state.last_action ? `${state.last_action.command} -> ${state.last_action.output}` : null}
            mode={state.mode}
            onUpdateGoalStatus={handleUpdateGoalStatus}
            state={state}
            world={world}
            autobioEntries={autobioEntries}
            onRollback={handleRollback}
            onApprovalDecision={handleApprovalDecision}
          />
        )}
      </main>
    </div>
  );
}

// Overview Panel Component
function OverviewPanel({
  focusGoalTitle,
  goals,
  latestActionLabel,
  mode,
  onUpdateGoalStatus,
  state,
  world,
  autobioEntries,
  onRollback,
  onApprovalDecision,
}: {
  focusGoalTitle: string | null;
  goals: Goal[];
  latestActionLabel: string | null;
  mode: BeingState["mode"];
  onUpdateGoalStatus: (goalId: string, status: Goal["status"]) => void;
  state: BeingState;
  world: InnerWorldState | null;
  autobioEntries: string[];
  onRollback?: (jobId: string) => void;
  onApprovalDecision?: (jobId: string, approved: boolean) => void;
}) {
  const isAwake = mode === "awake";

  return (
    <div className="overview-page">
      {/* Overview Cards */}
      <section className="overview-stage">
        <div className="overview-grid">
          <article className="overview-card overview-card--primary">
            <p className="overview-card__label">当前焦点</p>
            <p className="overview-card__value">{focusGoalTitle ?? "暂未锁定"}</p>
            <p className="overview-card__body">
              {state.current_thought ?? "现在没有新的显性想法。"}
            </p>
          </article>

          <article className="overview-card">
            <p className="overview-card__label">运行状态</p>
            <p className="overview-card__value">
              <span className={`status-badge status-badge--${mode}`}>
                {isAwake ? "运行中" : "休眠中"}
              </span>
            </p>
            <p className="overview-card__body">
              {isAwake ? "数字人正在自主运行，处理目标和任务。" : "数字人处于休眠状态，点击唤醒按钮启动。"}
            </p>
          </article>

          <article className="overview-card">
            <p className="overview-card__label">最近动作</p>
            <p className="overview-card__body">{latestActionLabel ?? "最近没有新的执行动作。"}</p>
          </article>
        </div>
      </section>

      {/* Inspector Grid - 1-1 Layout */}
      <section className="inspector-grid inspector-grid--balanced">
        <div className="inspector-grid__col">
          <StatusPanel error={""} focusGoalTitle={focusGoalTitle} state={state} onRollback={onRollback} onApprovalDecision={onApprovalDecision} />
        </div>
        <div className="inspector-grid__col">
          <WorldPanel world={world} />
        </div>
      </section>

      {/* Autobio Section */}
      <section className="autobio-section">
        <AutobioPanel entries={autobioEntries} />
      </section>

      {/* Goals Board */}
      <section className="mission-board">
        <GoalsPanel goals={goals} onUpdateGoalStatus={onUpdateGoalStatus} />
      </section>
    </div>
  );
}

function resolveRoute(hash: string): AppRoute {
  if (hash === "#/chat") return "chat";
  if (hash === "#/settings") return "settings";
  if (hash === "#/history") return "history";
  if (hash === "#/tools") return "tools";
  return "overview";
}

function routeToHash(route: AppRoute): string {
  if (route === "chat") return "#/chat";
  if (route === "settings") return "#/settings";
  if (route === "history") return "#/history";
  if (route === "tools") return "#/tools";
  return "#/";
}

function resolveFocusGoalTitle(state: BeingState, goals: Goal[]): string | null {
  if (state.active_goal_ids.length > 0) {
    const currentGoal = goals.find((goal) => goal.id === state.active_goal_ids[0]);
    if (currentGoal) {
      return currentGoal.title;
    }
  }

  return state.today_plan?.goal_title ?? null;
}

function renderFocusModeLabel(focusMode: BeingState["focus_mode"]): string {
  if (focusMode === "morning_plan") {
    return "晨间计划";
  }
  if (focusMode === "autonomy") {
    return "常规自主";
  }
  if (focusMode === "self_improvement") {
    return "自我修复";
  }
  return "休眠";
}

function mergeMessages(
  current: ChatEntry[],
  incoming: ChatHistoryMessage[],
): ChatEntry[] {
  const merged = new Map<string, ChatEntry>();

  for (const message of current) {
    merged.set(`${message.role}:${message.content}`, message);
  }

  incoming.forEach((message, index) => {
    const key = `${message.role}:${message.content}`;
    merged.set(key, {
      id: `${message.role}-${index}-${message.content}`,
      role: message.role,
      content: message.content,
    });
  });

  return Array.from(merged.values());
}

// ═════════════════════════════════════════
// History Page — 自编程历史记录页面
// ═════════════════════════════════════════

function HistoryPage({ onSelectRollback }: { onSelectRollback?: (jobId: string) => void }) {
  const [selectedEntry, setSelectedEntry] = useState<SelfImprovementHistoryEntry | null>(null);

  return (
    <div className="history-page">
      <HistoryPanel
        visible={true}
        onSelectEntry={(entry) => setSelectedEntry(entry)}
      />

      {/* 选中详情侧栏（可选） */}
      {selectedEntry ? (
        <aside className="history-detail">
          <header className="history-detail__header">
            <h3>详情</h3>
            <button type="button" className="btn btn--sm" onClick={() => setSelectedEntry(null)}>关闭</button>
          </header>
          <div className="history-detail__body">
            <dl className="history-detail__list">
              <dt>Job ID</dt><dd>{selectedEntry.job_id}</dd>
              <dt>目标区域</dt><dd>{selectedEntry.target_area}</dd>
              <dt>原因</dt><dd>{selectedEntry.reason}</dd>
              <dt>结果</dt><dd>{selectedEntry.outcome}</dd>
              <dt>状态</dt><dd>{historyStatusLabel(selectedEntry.status)}</dd>
              <dt>创建时间</dt><dd>{new Date(selectedEntry.created_at).toLocaleString("zh-CN")}</dd>
            </dl>

            {selectedEntry.touched_files.length > 0 ? (
              <div className="history-detail__section">
                <h4>触碰文件</h4>
                <ul className="history-detail__files">
                  {selectedEntry.touched_files.map((f: string) => <li key={f}><code>{f}</code></li>)}
                </ul>
              </div>
            ) : null}

            {selectedEntry.health_score != null ? (
              <div className="history-detail__section">
                <h4>健康度</h4>
                <span style={{ fontSize: "1.5rem", fontWeight: 700, color: healthColor(selectedEntry.health_score) }}>
                  {selectedEntry.health_score.toFixed(0)}
                </span>
                <span style={{ color: "var(--text-tertiary)", marginLeft: varStr("space-2") }}>分</span>
              </div>
            ) : null}

            {/* 回滚按钮 */}
            {onSelectRollback && selectedEntry.status === "applied" ? (
              <button
                type="button"
                className="btn btn--danger"
                onClick={() => {
                  onSelectRollback(selectedEntry.job_id);
                  setSelectedEntry(null);
                }}
                style={{ marginTop: varStr("space-4"), width: "100%" }}
              >
                ↩️ 回滚此操作
              </button>
            ) : null}
          </div>
        </aside>
      ) : null}
    </div>
  );
}

/** 辅助：获取 CSS 变量值 */
function varStr(name: string): string {
  return `var(--${name})`;
}

function historyStatusLabel(status: string): string {
  const map: Record<string, string> = {
    applied: "已生效", failed: "失败", verifying: "验证中",
    patching: "修补中", diagnosing: "诊断中", pending: "待开始",
    pending_approval: "待审批", rejected: "已拒绝",
  };
  return map[status] ?? status;
}

function healthColor(score: number): string {
  if (score >= 80) return "var(--success)";
  if (score >= 60) return "var(--info)";
  if (score >= 40) return "var(--warning)";
  return "var(--danger)";
}

function loadThemePreference(): "dark" | "light" {
  if (typeof window === "undefined") {
    return "dark";
  }
  const saved = localStorage.getItem("theme");
  if (saved === "light" || saved === "dark") {
    return saved;
  }
  // 检测系统偏好
  if (window.matchMedia && window.matchMedia("(prefers-color-scheme: light)").matches) {
    return "light";
  }
  return "dark";
}
