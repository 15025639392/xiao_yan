import type { Goal } from "../lib/api";

type GoalsPanelProps = {
  goals: Goal[];
  onUpdateGoalStatus: (goalId: string, status: Goal["status"]) => void;
};

export function GoalsPanel({ goals, onUpdateGoalStatus }: GoalsPanelProps) {
  const { chainedGroups, standaloneGoals } = groupGoals(goals);

  return (
    <section>
      <h2>Goals</h2>
      {goals.length === 0 ? <p>No active goals.</p> : null}
      {chainedGroups.map((group) => (
        <section key={group.chainId}>
          <h3>Timeline: {group.chainId}</h3>
          <p>{group.summary}</p>
          <ul>
            {group.goals.map((goal) => (
              <GoalItem key={goal.id} goal={goal} onUpdateGoalStatus={onUpdateGoalStatus} />
            ))}
          </ul>
        </section>
      ))}
      {standaloneGoals.length > 0 ? (
        <section>
          <h3>Standalone Goals</h3>
          <ul>
            {standaloneGoals.map((goal) => (
              <GoalItem key={goal.id} goal={goal} onUpdateGoalStatus={onUpdateGoalStatus} />
            ))}
          </ul>
        </section>
      ) : null}
    </section>
  );
}

type GoalItemProps = {
  goal: Goal;
  onUpdateGoalStatus: (goalId: string, status: Goal["status"]) => void;
};

function GoalItem({ goal, onUpdateGoalStatus }: GoalItemProps) {
  return (
    <li>
      <span>{goal.title}</span>
      <span> {goal.status}</span>
      {goal.chain_id ? <p>Chain: {goal.chain_id}</p> : null}
      <p>Generation: {goal.generation ?? 0}</p>
      {goal.parent_goal_id ? <p>Parent: {goal.parent_goal_id}</p> : null}
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
  );
}

function groupGoals(goals: Goal[]): {
  chainedGroups: Array<{ chainId: string; goals: Goal[]; summary: string }>;
  standaloneGoals: Goal[];
} {
  const chainedMap = new Map<string, Goal[]>();
  const standaloneGoals: Goal[] = [];

  goals.forEach((goal) => {
    if (!goal.chain_id) {
      standaloneGoals.push(goal);
      return;
    }

    const existing = chainedMap.get(goal.chain_id) ?? [];
    existing.push(goal);
    chainedMap.set(goal.chain_id, existing);
  });

  const chainedGroups = Array.from(chainedMap.entries()).map(([chainId, chainGoals]) => {
    const sortedGoals = sortGoalsByGeneration(chainGoals);

    return {
      chainId,
      goals: sortedGoals,
      summary: summarizeChain(sortedGoals),
    };
  });

  return { chainedGroups, standaloneGoals };
}

function sortGoalsByGeneration(goals: Goal[]): Goal[] {
  return [...goals].sort((left, right) => (left.generation ?? 0) - (right.generation ?? 0));
}

function summarizeChain(goals: Goal[]): string {
  const currentGoal = findCurrentGoal(goals);
  const currentGeneration = currentGoal?.generation ?? 0;
  const currentStatus = currentGoal?.status ?? "active";
  const currentTitle = currentGoal?.title ?? "unknown";

  return `Summary: ${goals.length} steps, current generation ${currentGeneration}, ${currentStatus} now on ${currentTitle}`;
}

function findCurrentGoal(goals: Goal[]): Goal | undefined {
  const highestGeneration = Math.max(...goals.map((goal) => goal.generation ?? 0));
  const latestGenerationGoals = goals.filter(
    (goal) => (goal.generation ?? 0) === highestGeneration,
  );

  return [...latestGenerationGoals].sort(
    (left, right) => getStatusPriority(left.status) - getStatusPriority(right.status),
  )[0];
}

function getStatusPriority(status: Goal["status"]): number {
  switch (status) {
    case "active":
      return 0;
    case "paused":
      return 1;
    case "completed":
      return 2;
    case "abandoned":
      return 3;
  }
}
