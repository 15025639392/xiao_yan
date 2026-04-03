import type { Goal } from "../lib/api";

type GoalsPanelProps = {
  goals: Goal[];
  onUpdateGoalStatus: (goalId: string, status: Goal["status"]) => void;
};

export function GoalsPanel({ goals, onUpdateGoalStatus }: GoalsPanelProps) {
  return (
    <section>
      <h2>Goals</h2>
      {goals.length === 0 ? <p>No active goals.</p> : null}
      <ul>
        {goals.map((goal) => (
          <li key={goal.id}>
            <span>{goal.title}</span>
            <span> {goal.status}</span>
            {goal.status !== "paused" ? (
              <button type="button" onClick={() => onUpdateGoalStatus(goal.id, "paused")}>
                Pause
              </button>
            ) : (
              <button type="button" onClick={() => onUpdateGoalStatus(goal.id, "active")}>
                Resume
              </button>
            )}
            {goal.status !== "completed" ? (
              <button type="button" onClick={() => onUpdateGoalStatus(goal.id, "completed")}>
                Complete
              </button>
            ) : null}
            {goal.status !== "abandoned" ? (
              <button type="button" onClick={() => onUpdateGoalStatus(goal.id, "abandoned")}>
                Abandon
              </button>
            ) : null}
          </li>
        ))}
      </ul>
    </section>
  );
}
