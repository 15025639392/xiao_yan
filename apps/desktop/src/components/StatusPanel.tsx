import type { BeingState } from "../lib/api";

type StatusPanelProps = {
  state: BeingState;
  error: string;
};

export function StatusPanel({ state, error }: StatusPanelProps) {
  return (
    <section>
      <p>Mode: {state.mode}</p>
      <p>Thought: {state.current_thought ?? "..."}</p>
      {error ? <p>{error}</p> : null}
    </section>
  );
}
