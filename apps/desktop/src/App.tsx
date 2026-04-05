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
          setError(err instanceof Error ? err.message : "sync failed");
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
      setError(err instanceof Error ? err.message : "wake failed");
    }
  }

  async function handleSleep() {
    try {
      setError("");
      setState(await sleep());
    } catch (err) {
      setError(err instanceof Error ? err.message : "sleep failed");
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
      setError(err instanceof Error ? err.message : "chat failed");
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
      setError(err instanceof Error ? err.message : "goal update failed");
    }
  }

  return (
    <main>
      <h1>Digital Being</h1>
      <StatusPanel error={error} focusGoalTitle={focusGoalTitle} state={state} />
      <WorldPanel world={world} />
      <AutobioPanel entries={autobioEntries} />
      <GoalsPanel goals={goals} onUpdateGoalStatus={handleUpdateGoalStatus} />
      <ChatPanel
        draft={draft}
        isSending={isSending}
        messages={messages}
        onDraftChange={setDraft}
        onSend={handleSend}
      />
      <button onClick={handleWake} type="button">
        Wake
      </button>
      <button onClick={handleSleep} type="button">
        Sleep
      </button>
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
