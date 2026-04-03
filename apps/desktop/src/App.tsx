import { useState } from "react";

import { ChatPanel } from "./components/ChatPanel";
import { StatusPanel } from "./components/StatusPanel";
import type { BeingState } from "./lib/api";
import { sleep, wake } from "./lib/api";

const initialState: BeingState = {
  mode: "sleeping",
  current_thought: null,
  active_goal_ids: [],
};

export default function App() {
  const [state, setState] = useState<BeingState>(initialState);
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

  return (
    <main>
      <h1>Digital Being</h1>
      <StatusPanel error={error} state={state} />
      <ChatPanel />
      <button onClick={handleWake} type="button">
        Wake
      </button>
      <button onClick={handleSleep} type="button">
        Sleep
      </button>
    </main>
  );
}
