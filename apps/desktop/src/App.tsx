import { useEffect, useState } from "react";

import { AutobioPanel } from "./components/AutobioPanel";
import { ChatPanel } from "./components/ChatPanel";
import type { ChatEntry } from "./components/ChatPanel";
import { GoalsPanel } from "./components/GoalsPanel";
import { StatusPanel } from "./components/StatusPanel";
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

type AppRoute = "overview" | "chat";

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
    <main className="console-shell">
      {/* Header with Navigation */}
      <header className="status-strip">
        <div className="status-strip__brand">
          <div className="status-strip__logo">🤖</div>
          <h1 className="status-strip__title">数字人控制台</h1>
        </div>

        <nav className="nav-tabs" aria-label="主导航">
          <button
            className={`nav-tab ${route === "overview" ? "nav-tab--active" : ""}`}
            onClick={() => handleNavigate("overview")}
            type="button"
          >
            <svg className="nav-tab__icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <rect x="3" y="3" width="7" height="7" rx="1" />
              <rect x="14" y="3" width="7" height="7" rx="1" />
              <rect x="14" y="14" width="7" height="7" rx="1" />
              <rect x="3" y="14" width="7" height="7" rx="1" />
            </svg>
            总览
          </button>
          <button
            className={`nav-tab ${route === "chat" ? "nav-tab--active" : ""}`}
            onClick={() => handleNavigate("chat")}
            type="button"
          >
            <svg className="nav-tab__icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
            </svg>
            对话
          </button>
        </nav>

        <div className="status-strip__meta">
          <div className="status-pill">
            <span className={`status-pill__dot status-pill__dot--${state.mode}`} />
            <span className="status-pill__label">状态</span>
            <span className="status-pill__value">{isAwake ? "运行中" : "休眠中"}</span>
          </div>
        </div>

        <div className="status-strip__actions">
          <button
            className="btn btn--primary"
            onClick={handleWake}
            type="button"
            disabled={isAwake}
          >
            唤醒
          </button>
          <button
            className="btn btn--secondary"
            onClick={handleSleep}
            type="button"
            disabled={!isAwake}
          >
            休眠
          </button>
        </div>
      </header>

      {/* Error Banner */}
      {error ? (
        <div className="error-banner">
          <strong>错误：</strong>
          {error}
        </div>
      ) : null}

      {/* Main Content */}
      {route === "chat" ? (
        <ChatPanel
          draft={draft}
          focusGoalTitle={focusGoalTitle}
          focusModeLabel={renderFocusModeLabel(state.focus_mode)}
          isSending={isSending}
          latestActionLabel={state.last_action ? `${state.last_action.command} -> ${state.last_action.output}` : null}
          messages={messages}
          modeLabel={isAwake ? "运行中" : "休眠中"}
          onDraftChange={setDraft}
          onSend={handleSend}
        />
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
        />
      )}
    </main>
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
}: {
  focusGoalTitle: string | null;
  goals: Goal[];
  latestActionLabel: string | null;
  mode: BeingState["mode"];
  onUpdateGoalStatus: (goalId: string, status: Goal["status"]) => void;
  state: BeingState;
  world: InnerWorldState | null;
  autobioEntries: string[];
}) {
  const isAwake = mode === "awake";

  return (
    <>
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

      {/* Inspector Grid - 2-1 Layout */}
      <section className="inspector-grid">
        <div className="inspector-grid__rail">
          <div className="inspector-grid__main">
            <StatusPanel error={""} focusGoalTitle={focusGoalTitle} state={state} />
          </div>
          <div className="inspector-grid__side">
            <WorldPanel world={world} />
          </div>
        </div>
        <div className="inspector-grid__bottom">
          <AutobioPanel entries={autobioEntries} />
        </div>
      </section>

      {/* Goals Board */}
      <section className="mission-board">
        <GoalsPanel goals={goals} onUpdateGoalStatus={onUpdateGoalStatus} />
      </section>
    </>
  );
}

function resolveRoute(hash: string): AppRoute {
  return hash === "#/chat" ? "chat" : "overview";
}

function routeToHash(route: AppRoute): string {
  return route === "chat" ? "#/chat" : "#/";
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
