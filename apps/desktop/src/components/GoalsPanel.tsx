import type { Goal } from "../lib/api";

type GoalsPanelProps = {
  goals: Goal[];
};

export function GoalsPanel({ goals }: GoalsPanelProps) {
  return (
    <section>
      <h2>Goals</h2>
      {goals.length === 0 ? <p>No active goals.</p> : null}
      <ul>
        {goals.map((goal) => (
          <li key={goal.id}>{goal.title}</li>
        ))}
      </ul>
    </section>
  );
}
