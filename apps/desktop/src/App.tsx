import { useState } from "react";

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
      <p>Mode: {state.mode}</p>
      <p>Thought: {state.current_thought ?? "..."}</p>
      <button onClick={handleWake} type="button">
        Wake
      </button>
      <button onClick={handleSleep} type="button">
        Sleep
      </button>
      {error ? <p>{error}</p> : null}
    </main>
  );
}
