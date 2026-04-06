import type { Goal } from "../lib/api";
import { ExecutionStatsPanel } from "./goals/ExecutionStatsPanel";
import { GoalBoard } from "./goals/GoalBoard";
import { GoalsChainsSection } from "./goals/GoalsChainsSection";
import { GoalsConfirmModal } from "./goals/GoalsConfirmModal";
import { GoalsHeaderActions } from "./goals/GoalsHeaderActions";
import { useGoalsPanelState } from "./goals/useGoalsPanelState";
import { EmptyState } from "./ui/EmptyState";
import { Panel } from "./ui/Panel";

type GoalsPanelProps = {
  goals: Goal[];
  onUpdateGoalStatus: (goalId: string, status: Goal["status"]) => void;
};

export function GoalsPanel({ goals, onUpdateGoalStatus }: GoalsPanelProps) {
  const {
    chainedGroups,
    columns,
    confirmModal,
    collapsedColumns,
    showExecutionPanel,
    executionStats,
    activeExecutions,
    loadingDecompose,
    openConfirm,
    closeConfirm,
    confirmAction,
    toggleColumn,
    handleDecomposeGoal,
    toggleExecutionPanel,
  } = useGoalsPanelState({ goals, onUpdateGoalStatus });

  return (
    <Panel
      icon="🎯"
      title="目标看板"
      subtitle="管理和追踪所有目标"
      actions={
        <GoalsHeaderActions
          goalsCount={goals.length}
          showExecutionPanel={showExecutionPanel}
          onToggleExecutionPanel={toggleExecutionPanel}
        />
      }
    >
      {showExecutionPanel && executionStats ? (
        <ExecutionStatsPanel executionStats={executionStats} activeExecutions={activeExecutions} goals={goals} />
      ) : null}

      {goals.length === 0 ? (
        <EmptyState size="small">
          <p>还没有目标。</p>
        </EmptyState>
      ) : null}

      <GoalsChainsSection chainedGroups={chainedGroups} />

      <GoalBoard
        columns={columns}
        collapsedColumns={collapsedColumns}
        onToggleColumn={toggleColumn}
        onAbandonClick={(goalId, goalTitle) => openConfirm(goalId, goalTitle, "abandon")}
        onCompleteClick={(goalId, goalTitle) => openConfirm(goalId, goalTitle, "complete")}
        onUpdateGoalStatus={onUpdateGoalStatus}
        onDecomposeGoal={handleDecomposeGoal}
        loadingDecompose={loadingDecompose}
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
