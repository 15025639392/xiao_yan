import { useMemo, useState } from "react";
import type { Goal, TaskExecution, TaskExecutionStats } from "../../lib/api";
import {
  decomposeGoal,
  fetchActiveTaskExecutions,
  fetchTaskExecutionStats,
  isRequestStatusError,
} from "../../lib/api";
import { groupGoals } from "./goalsUtils";

type GoalConfirmState = {
  isOpen: boolean;
  goalId: string;
  goalTitle: string;
  action: "abandon" | "complete";
};

type UseGoalsPanelStateArgs = {
  goals: Goal[];
  onUpdateGoalStatus: (goalId: string, status: Goal["status"]) => void;
};

const INITIAL_CONFIRM_STATE: GoalConfirmState = {
  isOpen: false,
  goalId: "",
  goalTitle: "",
  action: "abandon",
};

export function useGoalsPanelState({ goals, onUpdateGoalStatus }: UseGoalsPanelStateArgs) {
  const { chainedGroups, columns } = useMemo(() => groupGoals(goals), [goals]);
  const [confirmModal, setConfirmModal] = useState<GoalConfirmState>(INITIAL_CONFIRM_STATE);
  const [collapsedColumns, setCollapsedColumns] = useState<Set<string>>(new Set(["closed"]));
  const [showExecutionPanel, setShowExecutionPanel] = useState(false);
  const [executionStats, setExecutionStats] = useState<TaskExecutionStats | null>(null);
  const [activeExecutions, setActiveExecutions] = useState<TaskExecution[]>([]);
  const [loadingDecompose, setLoadingDecompose] = useState<Set<string>>(new Set());
  const [executionStatsSupported, setExecutionStatsSupported] = useState(true);
  const [goalDecomposeSupported, setGoalDecomposeSupported] = useState(true);

  function openConfirm(goalId: string, goalTitle: string, action: "abandon" | "complete") {
    setConfirmModal({ isOpen: true, goalId, goalTitle, action });
  }

  function closeConfirm() {
    setConfirmModal(INITIAL_CONFIRM_STATE);
  }

  function confirmAction() {
    if (confirmModal.goalId) {
      onUpdateGoalStatus(confirmModal.goalId, confirmModal.action === "abandon" ? "abandoned" : "completed");
    }
    closeConfirm();
  }

  function toggleColumn(columnId: string) {
    setCollapsedColumns((prev) => {
      const next = new Set(prev);
      if (next.has(columnId)) {
        next.delete(columnId);
      } else {
        next.add(columnId);
      }
      return next;
    });
  }

  async function loadExecutionStats() {
    try {
      const stats = await fetchTaskExecutionStats();
      setExecutionStats(stats);
      const executions = await fetchActiveTaskExecutions();
      setActiveExecutions(executions);
      setExecutionStatsSupported(true);
    } catch (error) {
      if (isRequestStatusError(error, 404)) {
        setExecutionStatsSupported(false);
        setExecutionStats(null);
        setActiveExecutions([]);
        return;
      }
      console.error("Failed to load execution stats:", error);
    }
  }

  async function handleDecomposeGoal(goalId: string) {
    if (!goalDecomposeSupported || loadingDecompose.has(goalId)) return;
    setLoadingDecompose((prev) => new Set([...prev, goalId]));
    try {
      await decomposeGoal(goalId);
    } catch (error) {
      if (isRequestStatusError(error, 404)) {
        setGoalDecomposeSupported(false);
        return;
      }
      console.error("Failed to decompose goal:", error);
    } finally {
      setLoadingDecompose((prev) => {
        const next = new Set(prev);
        next.delete(goalId);
        return next;
      });
    }
  }

  function toggleExecutionPanel() {
    setShowExecutionPanel((prev) => {
      if (!prev) {
        void loadExecutionStats();
      }
      return !prev;
    });
  }

  return {
    chainedGroups,
    columns,
    confirmModal,
    collapsedColumns,
    showExecutionPanel,
    executionStats,
    activeExecutions,
    loadingDecompose,
    executionStatsSupported,
    goalDecomposeSupported,
    openConfirm,
    closeConfirm,
    confirmAction,
    toggleColumn,
    handleDecomposeGoal,
    toggleExecutionPanel,
  };
}
