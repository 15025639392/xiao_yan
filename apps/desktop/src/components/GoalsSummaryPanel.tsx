import { useMemo, useState } from "react";
import type { FocusContext, Goal } from "../lib/api";
import { getFocusContextBadge, getFocusContextLines } from "../lib/focusContextPresentation";
import { GoalBoard } from "./goals/GoalBoard";
import { GoalsConfirmModal } from "./goals/GoalsConfirmModal";
import { GoalsHeaderActions } from "./goals/GoalsHeaderActions";
import { groupGoals } from "./goals/goalsUtils";
import { EmptyState } from "./ui/EmptyState";
import { Panel } from "./ui/Panel";
import { StatusBadge } from "./ui/StatusBadge";

type GoalsSummaryPanelProps = {
  goals: Goal[];
  focusGoalId?: string | null;
  focusGoalTitle?: string | null;
  focusContext?: FocusContext | null;
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

export function GoalsSummaryPanel({
  goals,
  focusGoalId,
  focusGoalTitle,
  focusContext,
  onUpdateGoalStatus,
}: GoalsSummaryPanelProps) {
  const { columns } = useMemo(() => groupGoals(goals), [goals]);
  const [collapsedColumns, setCollapsedColumns] = useState<Set<string>>(new Set(["closed"]));
  const [confirmModal, setConfirmModal] = useState<GoalConfirmState>(INITIAL_CONFIRM_STATE);
  const focusStatusBadge = getFocusContextBadge(focusContext);
  const focusContextLines = getFocusContextLines(focusContext);

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

      {focusGoalTitle ? (
        <section className="goals-summary-focus">
          <header className="goals-summary-focus__header">
            <div className="goals-summary-focus__title-wrap">
              <h3 className="goals-summary-focus__title">当前焦点正在这里</h3>
              <p className="goals-summary-focus__subtitle">{focusGoalTitle}</p>
            </div>
            {focusStatusBadge ? <StatusBadge tone={focusStatusBadge.tone}>{focusStatusBadge.label}</StatusBadge> : null}
          </header>
          {focusContextLines.map((line) => (
            <p key={line} className="goals-summary-focus__body">
              {line}
            </p>
          ))}
        </section>
      ) : null}

      <GoalBoard
        columns={columns}
        collapsedColumns={collapsedColumns}
        focusGoalId={focusGoalId}
        focusGoalTitle={focusGoalTitle}
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
