import { useEffect, useState } from "react";

import { ChatPanel } from "./components/ChatPanel";
import type { ChatEntry } from "./components/ChatPanel";
import { GoalsPanel } from "./components/GoalsPanel";
import { StatusPanel } from "./components/StatusPanel";
import type { BeingState, ChatHistoryMessage, Goal } from "./lib/api";
import {
  chat,
  fetchGoals,
  fetchMessages,
  fetchState,
  sleep,
  updateGoalStatus,
  wake,
} from "./lib/api";

const initialState: BeingState = {
  mode: "sleeping",
  current_thought: null,
  active_goal_ids: [],
};

export default function App() {
  const [state, setState] = useState<BeingState>(initialState);
  const [messages, setMessages] = useState<ChatEntry[]>([]);
  const [goals, setGoals] = useState<Goal[]>([]);
  const [draft, setDraft] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;

    async function syncRuntime() {
      try {
        const [nextState, nextMessages, nextGoals] = await Promise.all([
          fetchState(),
          fetchMessages(),
          fetchGoals(),
        ]);

        if (cancelled) {
          return;
        }

        setState(nextState);
        setMessages((current) => mergeMessages(current, nextMessages.messages));
        setGoals(nextGoals.goals);
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

      setGoals((current) =>
        current.map((goal) => (goal.id === updatedGoal.id ? updatedGoal : goal))
      );
      setState((current) => ({
        ...current,
        active_goal_ids: syncActiveGoalIds(current.active_goal_ids, updatedGoal),
      }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "goal update failed");
    }
  }

  return (
    <main>
      <h1>Digital Being</h1>
      <StatusPanel error={error} state={state} />
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

function syncActiveGoalIds(activeGoalIds: string[], goal: Goal): string[] {
  if (goal.status === "active") {
    return activeGoalIds.includes(goal.id) ? activeGoalIds : [...activeGoalIds, goal.id];
  }

  return activeGoalIds.filter((goalId) => goalId !== goal.id);
}
