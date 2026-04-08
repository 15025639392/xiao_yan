import { useEffect, useState } from "react";
import type { BeingState, EmotionState, RelationshipSummary } from "../lib/api";
import { fetchEmotionState, fetchMemorySummary } from "../lib/api";
import { subscribeAppRealtime } from "../lib/realtime";
import { ApprovalPanel } from "./ApprovalPanel";
import { MemoryRelationshipSummary } from "./memory/MemoryRelationshipSummary";
import { StartApprovalPanel } from "./StartApprovalPanel";
import { EmotionPanel } from "./status/EmotionPanel";
import { SelfProgrammingCooldownSettings } from "./status/SelfProgrammingCooldownSettings";
import { SelfProgrammingPanel } from "./status/SelfProgrammingPanel";
import { TodayPlanSection } from "./status/TodayPlanSection";
import { Panel } from "./ui/Panel";
import { StatusBadge } from "./ui/StatusBadge";
import { InlineAlert } from "./ui/InlineAlert";

type StatusPanelProps = {
  state: BeingState;
  error: string;
  focusGoalTitle?: string | null;
  onRollback?: (jobId: string) => void;
  onApprovalDecision?: (jobId: string, approved: boolean) => void;
};

export function StatusPanel({ state, error, onRollback, onApprovalDecision }: StatusPanelProps) {
  const planCompleted =
    state.today_plan?.steps.length && state.today_plan.steps.every((step) => step.status === "completed");
  const selfProgrammingJob = state.self_programming_job;
  const [emotionState, setEmotionState] = useState<EmotionState | null>(null);
  const [relationship, setRelationship] = useState<RelationshipSummary | null>(null);
  const [showEmotionDetails, setShowEmotionDetails] = useState(false);

  useEffect(() => {
    fetchEmotionState().then(setEmotionState).catch(console.error);
    fetchMemorySummary()
      .then((summary) => setRelationship(summary.relationship))
      .catch(() => setRelationship(null));
  }, [state.mode, state.focus_mode]);

  useEffect(() => {
    const unsubscribe = subscribeAppRealtime((event) => {
      const memoryPayload =
        event.type === "snapshot" ? event.payload.memory : event.type === "memory_updated" ? event.payload : null;
      if (!memoryPayload) {
        return;
      }

      setRelationship(memoryPayload.relationship ?? memoryPayload.summary.relationship ?? null);
    });

    return () => unsubscribe();
  }, []);

  const headerBadge = state.today_plan ? (
    <StatusBadge tone={planCompleted ? "completed" : "active"}>
      {planCompleted ? "已完成" : "进行中"}
    </StatusBadge>
  ) : null;

  return (
    <Panel icon="📋" title="今日计划" subtitle="当前日程与自我编程状态" actions={headerBadge}>
      {state.today_plan ? <TodayPlanSection plan={state.today_plan} planCompleted={Boolean(planCompleted)} /> : null}

      {emotionState ? (
        <EmotionPanel
          emotionState={emotionState}
          showDetails={showEmotionDetails}
          onToggleDetails={() => setShowEmotionDetails(!showEmotionDetails)}
        />
      ) : null}

      <MemoryRelationshipSummary relationship={relationship} />

      {selfProgrammingJob ? (
        selfProgrammingJob.status === "pending_start_approval"
        || selfProgrammingJob.status === "drafted"
        || selfProgrammingJob.status === "queued" ? (
          <StartApprovalPanel
            job={selfProgrammingJob}
            onDecision={(jobId) => {
              onApprovalDecision?.(jobId, true);
            }}
          />
        ) : selfProgrammingJob.status === "pending_approval" ? (
          <ApprovalPanel
            job={selfProgrammingJob}
            onDecision={(jobId, approved) => {
              onApprovalDecision?.(jobId, approved);
            }}
          />
        ) : (
          <SelfProgrammingPanel job={selfProgrammingJob} onRollback={onRollback} />
        )
      ) : null}

      {error ? (
        <InlineAlert tone="danger">{error}</InlineAlert>
      ) : null}

      {selfProgrammingJob ? <SelfProgrammingCooldownSettings /> : null}
    </Panel>
  );
}
