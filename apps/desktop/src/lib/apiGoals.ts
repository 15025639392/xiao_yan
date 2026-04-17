import { get, post } from "./apiClient";
import type { Goal } from "./api";

export type TaskExecution = {
  goal_id: string;
  started_at: string;
  completed_at?: string | null;
  status: Goal["status"];
  progress: number;
  error?: string | null;
  metadata?: Record<string, unknown>;
};

export type TaskExecutionStats = {
  total_tasks: number;
  completed: number;
  failed: number;
  abandoned: number;
  active: number;
  success_rate: number;
};

export type GoalDecompositionResult = {
  parent_goal_id: string;
  subgoals: Goal[];
  complexity: {
    level: "简单" | "中等" | "复杂";
    score: number;
    factors: Record<string, unknown>;
  };
};

export function decomposeGoal(goalId: string, maxSubtasks?: number): Promise<GoalDecompositionResult> {
  return get<GoalDecompositionResult>(`/goals/${goalId}/decompose?max_subtasks=${maxSubtasks ?? 5}`);
}

export function fetchTaskExecutionStats(): Promise<TaskExecutionStats> {
  return get<TaskExecutionStats>("/goals/execution/stats");
}

export function fetchActiveTaskExecutions(): Promise<TaskExecution[]> {
  return get<TaskExecution[]>("/goals/execution/active");
}

export function updateTaskProgress(goalId: string, progress: number): Promise<{ success: boolean }> {
  return post<{ success: boolean }>(`/goals/${goalId}/progress`, { progress });
}

export function fetchSchedulerStatus(): Promise<{
  max_concurrent: number;
  current_running: number;
  available_slots: number;
  running_task_ids: string[];
}> {
  return get<{
    max_concurrent: number;
    current_running: number;
    available_slots: number;
    running_task_ids: string[];
  }>("/goals/scheduler/status");
}
