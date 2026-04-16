import { useEffect, useState } from "react";
import type {
  Goal,
  GoalAdmissionConfigHistoryEntry,
  GoalAdmissionCandidateSnapshot,
  GoalAdmissionRuntimeConfig,
  GoalAdmissionStats,
  RelationshipSummary,
} from "../lib/api";
import {
  fetchGoalAdmissionConfigHistory,
  fetchGoalAdmissionCandidates,
  fetchGoalAdmissionStats,
  fetchMemorySummary,
  rollbackGoalAdmissionConfig,
  updateGoalAdmissionConfig,
} from "../lib/api";
import { subscribeAppRealtime } from "../lib/realtime";
import { GoalsAdmissionCandidates } from "./goals/GoalsAdmissionCandidates";
import { GoalsAdmissionOverview } from "./goals/GoalsAdmissionOverview";
import { ExecutionStatsPanel } from "./goals/ExecutionStatsPanel";
import { GoalBoard } from "./goals/GoalBoard";
import { GoalsChainsSection } from "./goals/GoalsChainsSection";
import { GoalsConfirmModal } from "./goals/GoalsConfirmModal";
import { GoalsHeaderActions } from "./goals/GoalsHeaderActions";
import { GoalsRelationshipGuidance } from "./goals/GoalsRelationshipGuidance";
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
  const [admissionStats, setAdmissionStats] = useState<GoalAdmissionStats | null>(null);
  const [admissionCandidates, setAdmissionCandidates] = useState<GoalAdmissionCandidateSnapshot | null>(null);
  const [admissionConfigHistory, setAdmissionConfigHistory] = useState<GoalAdmissionConfigHistoryEntry[]>([]);
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

  function syncAdmissionFromRuntime(runtimePayload: {
    goal_admission_stats?: GoalAdmissionStats | null;
    goal_admission_candidates?: GoalAdmissionCandidateSnapshot | null;
  }) {
    if (runtimePayload.goal_admission_stats !== undefined) {
      setAdmissionStats(runtimePayload.goal_admission_stats ?? null);
    }
    if (runtimePayload.goal_admission_candidates !== undefined) {
      setAdmissionCandidates(runtimePayload.goal_admission_candidates ?? null);
    }
  }

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
        const runtimePayload =
          event.type === "snapshot" ? event.payload.runtime : event.type === "runtime_updated" ? event.payload : null;
        if (runtimePayload) {
          syncAdmissionFromRuntime(runtimePayload);
        }
        return;
      }

      setRelationship(memoryPayload.relationship ?? memoryPayload.summary.relationship ?? null);

      const runtimePayload =
        event.type === "snapshot" ? event.payload.runtime : event.type === "runtime_updated" ? event.payload : null;
      if (runtimePayload) {
        syncAdmissionFromRuntime(runtimePayload);
      }
    });

    return () => unsubscribe();
  }, [isSummary]);

  async function handleUpdateAdmissionThresholds(patch: Partial<GoalAdmissionRuntimeConfig>): Promise<void> {
    await updateGoalAdmissionConfig(patch);
    const [latest, history] = await Promise.all([
      fetchGoalAdmissionStats(),
      fetchGoalAdmissionConfigHistory(10),
    ]);
    setAdmissionStats(latest);
    setAdmissionConfigHistory(history.items);
  }

  async function handleRollbackAdmissionThresholds(): Promise<void> {
    await rollbackGoalAdmissionConfig();
    const [latest, history] = await Promise.all([
      fetchGoalAdmissionStats(),
      fetchGoalAdmissionConfigHistory(10),
    ]);
    setAdmissionStats(latest);
    setAdmissionConfigHistory(history.items);
  }

  useEffect(() => {
    if (isSummary) {
      return;
    }
    let cancelled = false;

    fetchGoalAdmissionStats()
      .then((stats) => {
        if (!cancelled) {
          setAdmissionStats(stats);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setAdmissionStats(null);
        }
      });

    fetchGoalAdmissionCandidates()
      .then((snapshot) => {
        if (!cancelled) {
          setAdmissionCandidates(snapshot);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setAdmissionCandidates(null);
        }
      });

    fetchGoalAdmissionConfigHistory(10)
      .then((history) => {
        if (!cancelled) {
          setAdmissionConfigHistory(history.items);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setAdmissionConfigHistory([]);
        }
      });

    return () => {
      cancelled = true;
    };
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

      {!isSummary ? <GoalsRelationshipGuidance relationship={relationship} /> : null}
      {!isSummary ? (
        <GoalsAdmissionOverview
          stats={admissionStats}
          history={admissionConfigHistory}
          onUpdateStabilityThresholds={handleUpdateAdmissionThresholds}
          onRollbackStabilityThresholds={handleRollbackAdmissionThresholds}
        />
      ) : null}
      {!isSummary ? <GoalsAdmissionCandidates snapshot={admissionCandidates} /> : null}

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
