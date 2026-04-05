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

  return (
    <main className="console-shell">
      <section className="command-deck">
        <div className="section-heading">
          <p className="section-kicker">数字人控制台</p>
          <h1 className="section-title">指挥台</h1>
          <p className="section-summary">
            在一个界面里查看她的在线状态、当前阶段、专注目标和实时对话。
          </p>
        </div>
        <div className="command-deck__grid">
          <article className="command-card">
            <p className="command-card__label">在线状态</p>
            <p className="command-card__value">{renderModeLabel(state.mode)}</p>
          </article>
          <article className="command-card">
            <p className="command-card__label">当前阶段</p>
            <p className="command-card__value">{renderFocusModeLabel(state.focus_mode)}</p>
          </article>
          <article className="command-card">
            <p className="command-card__label">当前专注目标</p>
            <p className="command-card__value">{focusGoalTitle ?? "暂未锁定"}</p>
          </article>
          <article className="command-card">
            <p className="command-card__label">同步状态</p>
            <p className="command-card__value">{error ? "需要重试" : "每 5 秒同步"}</p>
          </article>
        </div>
        <div className="command-deck__actions">
          <button className="soft-button soft-button--primary" onClick={handleWake} type="button">
            唤醒
          </button>
          <button className="soft-button" onClick={handleSleep} type="button">
            休眠
          </button>
        </div>
      </section>

      <section className="workspace-grid">
        <div className="workspace-grid__primary">
          <ChatPanel
            draft={draft}
            isSending={isSending}
            messages={messages}
            onDraftChange={setDraft}
            onSend={handleSend}
          />
        </div>
        <div className="workspace-grid__rail">
          <StatusPanel error={error} focusGoalTitle={focusGoalTitle} state={state} />
          <WorldPanel world={world} />
          <AutobioPanel entries={autobioEntries} />
        </div>
      </section>

      <section className="mission-board">
        <div className="section-heading section-heading--compact">
          <p className="section-kicker">任务推进</p>
          <h2 className="section-title">目标看板</h2>
        </div>
        <GoalsPanel goals={goals} onUpdateGoalStatus={handleUpdateGoalStatus} />
      </section>
    </main>
  );
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

function renderModeLabel(mode: BeingState["mode"]): string {
  return mode === "awake" ? "运行中" : "休眠中";
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
