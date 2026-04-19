import { useEffect, useState } from "react";
import type { BeingState, EmotionState, FocusContext, MacConsoleBootstrapStatus, RelationshipSummary } from "../lib/api";
import { fetchEmotionState, fetchMemorySummary } from "../lib/api";
import { getFocusEffortLines, getFocusEffortTitle } from "../lib/focusEffortPresentation";
import { getFocusContextBadge, getFocusContextLines } from "../lib/focusContextPresentation";
import { formatRelativeTimeZh } from "../lib/utils/time";
import { subscribeAppRealtime } from "../lib/realtime";
import { MemoryRelationshipSummary } from "./memory/MemoryRelationshipSummary";
import { EmotionPanel } from "./status/EmotionPanel";
import { Panel } from "./ui/Panel";
import { StatusBadge } from "./ui/StatusBadge";
import { InlineAlert } from "./ui/InlineAlert";

type StatusPanelProps = {
  state: BeingState;
  macConsoleStatus?: MacConsoleBootstrapStatus | null;
  error: string;
  focusGoalTitle?: string | null;
  focusContext?: FocusContext | null;
  variant?: "full" | "compact";
};

export function StatusPanel({
  state,
  macConsoleStatus,
  error,
  focusGoalTitle,
  focusContext,
  variant = "full",
}: StatusPanelProps) {
  const isCompact = variant === "compact";
  const [emotionState, setEmotionState] = useState<EmotionState | null>(null);
  const [relationship, setRelationship] = useState<RelationshipSummary | null>(null);
  const [showEmotionDetails, setShowEmotionDetails] = useState(false);

  useEffect(() => {
    if (isCompact) {
      return;
    }
    fetchEmotionState().then(setEmotionState).catch(console.error);
    fetchMemorySummary()
      .then((summary) => setRelationship(summary.relationship))
      .catch(() => setRelationship(null));
  }, [isCompact, state.mode, state.focus_mode]);

  useEffect(() => {
    if (isCompact) {
      return;
    }
    const unsubscribe = subscribeAppRealtime((event) => {
      const memoryPayload =
        event.type === "snapshot" ? event.payload.memory : event.type === "memory_updated" ? event.payload : null;
      if (!memoryPayload) {
        return;
      }

      setRelationship(memoryPayload.relationship ?? memoryPayload.summary.relationship ?? null);
    });

    return () => unsubscribe();
  }, [isCompact]);

  const environmentTone = !macConsoleStatus
    ? "paused"
    : macConsoleStatus.healthy
      ? "completed"
      : "abandoned";
  const environmentLabel = renderMacConsoleStateLabel(macConsoleStatus?.state);
  const checkedAtLabel = macConsoleStatus?.checked_at
    ? formatRelativeTimeZh(macConsoleStatus.checked_at, { spacing: "spaced", dateFallback: "short" })
    : "";
  const focusContextLines = getFocusContextLines(focusContext, state.focus_context?.prompt_summary);
  const focusStatusBadge = getFocusContextBadge(focusContext);
  const focusEffortTitle = getFocusEffortTitle(state.focus_effort);
  const focusEffortLines = getFocusEffortLines(state.focus_effort);
  const focusSubjectWhyNow = state.focus_subject?.why_now?.trim() ?? "";

  return (
    <Panel icon="📋" title="眼下状态" subtitle="当前牵挂与生活状态">
      {focusGoalTitle ? (
        <section className="focus-status-card">
          <header className="focus-status-card__header">
            <div className="focus-status-card__title-wrap">
              <h4 className="focus-status-card__title">当前焦点</h4>
              <p className="focus-status-card__subtitle">{focusGoalTitle}</p>
            </div>
            {focusStatusBadge ? <StatusBadge tone={focusStatusBadge.tone}>{focusStatusBadge.label}</StatusBadge> : null}
          </header>
          {focusSubjectWhyNow ? <p className="focus-status-card__body">{focusSubjectWhyNow}</p> : null}
          {!focusSubjectWhyNow
            ? focusContextLines.map((line) => (
                <p key={line} className="focus-status-card__body">
                  {line}
                </p>
              ))
            : null}
        </section>
      ) : null}

      {state.focus_effort ? (
        <section className="focus-status-card">
          <header className="focus-status-card__header">
            <div className="focus-status-card__title-wrap">
              <h4 className="focus-status-card__title">{focusEffortTitle ?? "刚刚围绕焦点做了这件事"}</h4>
              <p className="focus-status-card__subtitle">{state.focus_effort.goal_title}</p>
            </div>
          </header>
          {focusEffortLines.map((line) => (
            <p key={line} className="focus-status-card__body">
              {line}
            </p>
          ))}
        </section>
      ) : null}

      {macConsoleStatus ? (
        <section className="environment-status-card">
          <header className="environment-status-card__header">
            <div className="environment-status-card__title-wrap">
              <h4 className="environment-status-card__title">身体环境（mac 控制台）</h4>
              <p className="environment-status-card__subtitle">启动时会先做一次自检，缺失项也会尽量自动补齐。</p>
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
      {!isCompact && emotionState ? (
        <EmotionPanel
          emotionState={emotionState}
          showDetails={showEmotionDetails}
          onToggleDetails={() => setShowEmotionDetails(!showEmotionDetails)}
        />
      ) : null}

      {!isCompact ? <MemoryRelationshipSummary relationship={relationship} /> : null}

      {error ? (
        <InlineAlert tone="danger">{error}</InlineAlert>
      ) : null}
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
