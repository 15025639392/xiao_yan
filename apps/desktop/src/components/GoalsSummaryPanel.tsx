import { useMemo, useState } from "react";
import type { Goal } from "../lib/api";
import { GoalBoard } from "./goals/GoalBoard";
import { GoalsConfirmModal } from "./goals/GoalsConfirmModal";
import { GoalsHeaderActions } from "./goals/GoalsHeaderActions";
import { groupGoals } from "./goals/goalsUtils";
import { EmptyState } from "./ui/EmptyState";
import { Panel } from "./ui/Panel";

type GoalsSummaryPanelProps = {
  goals: Goal[];
  onUpdateGoalStatus: (goalId: string, status: Goal["status"]) => void;
};

type GoalConfirmState = {
  isOpen: boolean;
  goalId: string;
  goalTitle: string;
  action: "abandon" | "complete";
};

const INITIAL_CONFIRM_STATE: GoalConfirmState = {
  isOpen: false,
  goalId: "",
  goalTitle: "",
  action: "abandon",
};

export function GoalsSummaryPanel({ goals, onUpdateGoalStatus }: GoalsSummaryPanelProps) {
  const { columns } = useMemo(() => groupGoals(goals), [goals]);
  const [collapsedColumns, setCollapsedColumns] = useState<Set<string>>(new Set(["closed"]));
  const [confirmModal, setConfirmModal] = useState<GoalConfirmState>(INITIAL_CONFIRM_STATE);

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

  return (
    <Panel
      icon="🎯"
      title="目标看板"
      subtitle="默认首页只保留核心目标推进"
      actions={
        <GoalsHeaderActions
          goalsCount={goals.length}
          executionStatsSupported={false}
          showExecutionPanel={false}
          onToggleExecutionPanel={() => {}}
        />
      }
    >
      {goals.length === 0 ? (
        <EmptyState size="small">
          <p>还没有目标。</p>
        </EmptyState>
      ) : null}

      <GoalBoard
        columns={columns}
        collapsedColumns={collapsedColumns}
        relationship={null}
        onToggleColumn={toggleColumn}
        onAbandonClick={(goalId, goalTitle) => openConfirm(goalId, goalTitle, "abandon")}
        onCompleteClick={(goalId, goalTitle) => openConfirm(goalId, goalTitle, "complete")}
        onUpdateGoalStatus={onUpdateGoalStatus}
        onDecomposeGoal={() => {}}
        loadingDecompose={new Set()}
        decomposeSupported={false}
      />

      <GoalsConfirmModal
        isOpen={confirmModal.isOpen}
        goalTitle={confirmModal.goalTitle}
        action={confirmModal.action}
        onConfirm={confirmAction}
        onCancel={closeConfirm}
      />
    </Panel>
  );
}
