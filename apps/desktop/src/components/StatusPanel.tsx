import { useEffect, useState } from "react";
import type { BeingState, EmotionState, MacConsoleBootstrapStatus, RelationshipSummary } from "../lib/api";
import { fetchEmotionState, fetchMemorySummary } from "../lib/api";
import { formatRelativeTimeZh } from "../lib/utils/time";
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
  macConsoleStatus?: MacConsoleBootstrapStatus | null;
  error: string;
  focusGoalTitle?: string | null;
  onRollback?: (jobId: string) => void;
  onApprovalDecision?: (jobId: string, approved: boolean) => void;
};

export function StatusPanel({ state, macConsoleStatus, error, onRollback, onApprovalDecision }: StatusPanelProps) {
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

  const environmentTone = !macConsoleStatus
    ? "paused"
    : macConsoleStatus.healthy
      ? "completed"
      : "abandoned";
  const environmentLabel = renderMacConsoleStateLabel(macConsoleStatus?.state);
  const checkedAtLabel = macConsoleStatus?.checked_at
    ? formatRelativeTimeZh(macConsoleStatus.checked_at, { spacing: "spaced", dateFallback: "short" })
    : "";

  return (
    <Panel icon="📋" title="今日计划" subtitle="当前日程与自我编程状态" actions={headerBadge}>
      {macConsoleStatus ? (
        <section className="environment-status-card">
          <header className="environment-status-card__header">
            <div className="environment-status-card__title-wrap">
              <h4 className="environment-status-card__title">身体环境（mac 控制台）</h4>
              <p className="environment-status-card__subtitle">系统会在启动时自动自检并尝试补齐。</p>
            </div>
            <StatusBadge tone={environmentTone}>{environmentLabel}</StatusBadge>
          </header>
          <p className="environment-status-card__summary">{macConsoleStatus.summary}</p>
          <dl className="environment-status-card__meta">
            <div>
              <dt>平台</dt>
              <dd>{macConsoleStatus.platform}</dd>
            </div>
            <div>
              <dt>最近检查</dt>
              <dd>{checkedAtLabel || "未知"}</dd>
            </div>
            <div>
              <dt>自动补齐</dt>
              <dd>{macConsoleStatus.attempted_autofix ? "已尝试" : "未触发"}</dd>
            </div>
          </dl>
        </section>
      ) : null}

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

function renderMacConsoleStateLabel(state: MacConsoleBootstrapStatus["state"] | undefined): string {
  if (state === "check_passed") return "环境正常";
  if (state === "autofix_succeeded") return "已自愈";
  if (state === "autofix_failed") return "需人工处理";
  if (state === "script_missing") return "脚本缺失";
  if (state === "disabled") return "已关闭";
  if (state === "skipped_non_macos") return "非 mac 跳过";
  if (state === "check_error" || state === "autofix_error") return "执行异常";
  return "状态未知";
}
