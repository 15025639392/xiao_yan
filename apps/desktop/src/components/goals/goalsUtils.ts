import type { Goal } from "../../lib/api";

export type GoalChainGroup = {
  chainId: string;
  goals: Goal[];
  summary: string;
};

export type GoalColumn = {
  id: "active" | "paused" | "closed";
  title: string;
  description: string;
  goals: Goal[];
};

export function renderGoalStatus(status: Goal["status"]): string {
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

export function groupGoals(goals: Goal[]): {
  chainedGroups: GoalChainGroup[];
  columns: GoalColumn[];
} {
  const chainedMap = new Map<string, Goal[]>();

  goals.forEach((goal) => {
    if (goal.chain_id) {
      const existing = chainedMap.get(goal.chain_id) ?? [];
      existing.push(goal);
      chainedMap.set(goal.chain_id, existing);
    }
  });

  const chainedGroups = Array.from(chainedMap.entries()).map(([chainId, chainGoals]) => {
    const sortedGoals = sortGoalsByGeneration(chainGoals);
    return {
      chainId,
      goals: sortedGoals,
      summary: summarizeChain(sortedGoals),
    };
  });

  const columns: GoalColumn[] = [
    {
      id: "active",
      title: "当前推进",
      description: "正在积极进行的目标。",
      goals: goals.filter((goal) => goal.status === "active"),
    },
    {
      id: "paused",
      title: "等待恢复",
      description: "已暂停但可随时恢复的目标。",
      goals: goals.filter((goal) => goal.status === "paused"),
    },
    {
      id: "closed",
      title: "已收束",
      description: "已完成或已放弃的目标。",
      goals: goals.filter((goal) => goal.status === "completed" || goal.status === "abandoned"),
    },
  ];

  return { chainedGroups, columns };
}

function sortGoalsByGeneration(goals: Goal[]): Goal[] {
  return [...goals].sort((left, right) => (left.generation ?? 0) - (right.generation ?? 0));
}

function summarizeChain(goals: Goal[]): string {
  const currentGoal = findCurrentGoal(goals);
  const currentGeneration = currentGoal?.generation ?? 0;
  const currentStatus = currentGoal?.status ?? "active";
  const currentTitle = currentGoal?.title ?? "未知目标";

  return `共 ${goals.length} 步，当前第 ${currentGeneration} 代，${renderGoalStatus(currentStatus)}，"${currentTitle}"`;
}

function findCurrentGoal(goals: Goal[]): Goal | undefined {
  const highestGeneration = Math.max(...goals.map((goal) => goal.generation ?? 0));
  const latestGenerationGoals = goals.filter((goal) => (goal.generation ?? 0) === highestGeneration);

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

