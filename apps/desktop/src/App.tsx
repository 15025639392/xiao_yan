import { useState } from "react";

import { ChatPanel } from "./components/ChatPanel";
import type { ChatEntry } from "./components/ChatPanel";
import { StatusPanel } from "./components/StatusPanel";
import type { BeingState } from "./lib/api";
import { chat, sleep, wake } from "./lib/api";

const initialState: BeingState = {
  mode: "sleeping",
  current_thought: null,
  active_goal_ids: [],
};

export default function App() {
  const [state, setState] = useState<BeingState>(initialState);
  const [messages, setMessages] = useState<ChatEntry[]>([]);
  const [draft, setDraft] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState("");

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

  return (
    <main>
      <h1>Digital Being</h1>
      <StatusPanel error={error} state={state} />
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
