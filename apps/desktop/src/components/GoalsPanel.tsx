import { useEffect, useState } from "react";
import type { Goal, RelationshipSummary } from "../lib/api";
import { fetchMemorySummary } from "../lib/api";
import { subscribeAppRealtime } from "../lib/realtime";
import { ExecutionStatsPanel } from "./goals/ExecutionStatsPanel";
import { GoalBoard } from "./goals/GoalBoard";
import { GoalsChainsSection } from "./goals/GoalsChainsSection";
import { GoalsConfirmModal } from "./goals/GoalsConfirmModal";
import { GoalsGovernanceSection } from "./goals/GoalsGovernanceSection";
import { GoalsHeaderActions } from "./goals/GoalsHeaderActions";
import { useGoalsPanelState } from "./goals/useGoalsPanelState";
import { EmptyState } from "./ui/EmptyState";
import { Panel } from "./ui/Panel";

type GoalsPanelProps = {
  goals: Goal[];
  onUpdateGoalStatus: (goalId: string, status: Goal["status"]) => void;
  mode?: "full" | "summary";
};

export function GoalsPanel({ goals, onUpdateGoalStatus, mode = "full" }: GoalsPanelProps) {
  const isSummary = mode === "summary";
  const [relationship, setRelationship] = useState<RelationshipSummary | null>(null);
  const {
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
  } = useGoalsPanelState({ goals, onUpdateGoalStatus });

  useEffect(() => {
    if (isSummary) {
      return;
    }
    fetchMemorySummary()
      .then((summary) => setRelationship(summary.relationship))
      .catch(() => setRelationship(null));

    const unsubscribe = subscribeAppRealtime((event) => {
      const memoryPayload =
        event.type === "snapshot" ? event.payload.memory : event.type === "memory_updated" ? event.payload : null;
      if (!memoryPayload) {
        return;
      }
      setRelationship(memoryPayload.relationship ?? memoryPayload.summary.relationship ?? null);
    });

    return () => unsubscribe();
  }, [isSummary]);

  return (
    <Panel
      icon="🎯"
      title="目标看板"
      subtitle={isSummary ? "默认首页只保留核心目标推进" : "管理和追踪所有目标"}
      actions={
        <GoalsHeaderActions
          goalsCount={goals.length}
          executionStatsSupported={!isSummary && executionStatsSupported}
          showExecutionPanel={showExecutionPanel}
          onToggleExecutionPanel={toggleExecutionPanel}
        />
      }
    >
      {!isSummary && showExecutionPanel && executionStats ? (
        <ExecutionStatsPanel executionStats={executionStats} activeExecutions={activeExecutions} goals={goals} />
      ) : null}

      {!isSummary ? <GoalsGovernanceSection relationship={relationship} /> : null}

      {goals.length === 0 ? (
        <EmptyState size="small">
          <p>还没有目标。</p>
        </EmptyState>
      ) : null}

      {!isSummary ? <GoalsChainsSection chainedGroups={chainedGroups} /> : null}

      <GoalBoard
        columns={columns}
        collapsedColumns={collapsedColumns}
        relationship={relationship}
        onToggleColumn={toggleColumn}
        onAbandonClick={(goalId, goalTitle) => openConfirm(goalId, goalTitle, "abandon")}
        onCompleteClick={(goalId, goalTitle) => openConfirm(goalId, goalTitle, "complete")}
        onUpdateGoalStatus={onUpdateGoalStatus}
        onDecomposeGoal={handleDecomposeGoal}
        loadingDecompose={loadingDecompose}
        decomposeSupported={!isSummary && goalDecomposeSupported}
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
