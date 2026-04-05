import type { Goal } from "../lib/api";

type GoalsPanelProps = {
  goals: Goal[];
  onUpdateGoalStatus: (goalId: string, status: Goal["status"]) => void;
};

export function GoalsPanel({ goals, onUpdateGoalStatus }: GoalsPanelProps) {
  const { chainedGroups, standaloneGoals } = groupGoals(goals);

  return (
    <section className="panel panel--board">
      <div className="panel__header">
        <div>
          <p className="panel__eyebrow">任务推进</p>
          <h2 className="panel__title">目标看板</h2>
        </div>
      </div>
      {goals.length === 0 ? <p className="empty-state">尚无目标。</p> : null}
      {chainedGroups.length > 0 ? (
        <section className="goal-section">
          <div className="goal-section__header">
            <h3>目标链</h3>
            <p>按目标链展示每一代推进状态。</p>
          </div>
          <div className="goal-chain-list">
            {chainedGroups.map((group) => (
              <section key={group.chainId} className="goal-chain">
                <div className="goal-chain__header">
                  <h4>链路 {group.chainId}</h4>
                  <p>{group.summary}</p>
                </div>
                <ul className="goal-list">
                  {group.goals.map((goal) => (
                    <GoalItem key={goal.id} goal={goal} onUpdateGoalStatus={onUpdateGoalStatus} />
                  ))}
                </ul>
              </section>
            ))}
          </div>
        </section>
      ) : null}
      {standaloneGoals.length > 0 ? (
        <section className="goal-section">
          <div className="goal-section__header">
            <h3>独立目标</h3>
            <p>暂未归入目标链的独立任务。</p>
          </div>
          <ul className="goal-list">
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
    <li className="goal-card">
      <div className="goal-card__top">
        <div className="goal-card__content">
          <p className="goal-card__title">{goal.title}</p>
          <div className="goal-card__meta">
            {goal.chain_id ? <span>链路：{goal.chain_id}</span> : null}
            <span>第 {goal.generation ?? 0} 代</span>
            {goal.parent_goal_id ? <span>上级目标：{goal.parent_goal_id}</span> : null}
          </div>
        </div>
        <span className={`status-badge status-badge--goal status-badge--${goal.status}`}>
          {renderGoalStatus(goal.status)}
        </span>
      </div>
      <div className="goal-card__actions">
        {goal.status === "active" ? (
          <button
            className="soft-button soft-button--small"
            type="button"
            onClick={() => onUpdateGoalStatus(goal.id, "paused")}
          >
            暂停
          </button>
        ) : null}
        {goal.status === "paused" ? (
          <button
            className="soft-button soft-button--small"
            type="button"
            onClick={() => onUpdateGoalStatus(goal.id, "active")}
          >
            恢复
          </button>
        ) : null}
        {goal.status !== "completed" && goal.status !== "abandoned" ? (
          <button
            className="soft-button soft-button--small"
            type="button"
            onClick={() => onUpdateGoalStatus(goal.id, "completed")}
          >
            完成
          </button>
        ) : null}
        {goal.status !== "abandoned" && goal.status !== "completed" ? (
          <button
            className="soft-button soft-button--small"
            type="button"
            onClick={() => onUpdateGoalStatus(goal.id, "abandoned")}
          >
            放弃
          </button>
        ) : null}
      </div>
    </li>
  );
}

function renderGoalStatus(status: Goal["status"]): string {
  switch (status) {
    case "active":
      return "推进中";
    case "paused":
      return "已暂停";
    case "completed":
      return "已完成";
    case "abandoned":
      return "已放弃";
  }
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
  const currentTitle = currentGoal?.title ?? "未知目标";

  return `共 ${goals.length} 步，当前推进到第 ${currentGeneration} 代，状态为${renderGoalStatus(currentStatus)}，当前目标是“${currentTitle}”`;
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
