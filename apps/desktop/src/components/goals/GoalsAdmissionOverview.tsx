import { useEffect, useRef, useState } from "react";
import type {
  GoalAdmissionConfigHistoryEntry,
  GoalAdmissionRuntimeConfig,
  GoalAdmissionStats,
} from "../../lib/api";
import { MetricCard, SurfaceCard } from "../ui";

type GoalsAdmissionOverviewProps = {
  stats: GoalAdmissionStats | null;
  history?: GoalAdmissionConfigHistoryEntry[];
  onUpdateStabilityThresholds?: (patch: Partial<GoalAdmissionRuntimeConfig>) => Promise<void>;
  onRollbackStabilityThresholds?: () => Promise<void>;
};

const DEFAULT_WARNING_RATE = 0.6;
const DEFAULT_DANGER_RATE = 0.35;
const UNDO_WINDOW_MS = 5000;

function describeMode(mode: GoalAdmissionStats["mode"]): string {
  if (mode === "off") {
    return "off 模式：当前不做准入守门，所有目标都会直接落地。";
  }
  if (mode === "enforce") {
    return "enforce 模式：当前会按准入规则直接拦截、延后或放行目标。";
  }
  return "shadow 模式：当前先观测建议，不直接拦截目标落地。";
}

function formatThreshold(label: string, minScore: number, deferScore: number): string {
  return `${label} ≥ ${minScore.toFixed(2)} 直接通过，≥ ${deferScore.toFixed(2)} 进入延后观察。`;
}

type StabilityRateTone = "muted" | "success" | "warning" | "danger";

function describeStabilityRate(rate: number | null): { text: string; tone: StabilityRateTone } {
  if (rate === null) {
    return { text: "24h 稳定率暂无样本。", tone: "muted" };
  }
  const percentage = `${(rate * 100).toFixed(1)}%`;
  if (rate >= 0.75) {
    return { text: `24h 稳定率 ${percentage}（健康）。`, tone: "success" };
  }
  if (rate >= 0.5) {
    return { text: `24h 稳定率 ${percentage}（需关注）。`, tone: "warning" };
  }
  return { text: `24h 稳定率 ${percentage}（告警）。`, tone: "danger" };
}

function buildStabilityAlert(
  stats: GoalAdmissionStats,
  overrides?: { warningRate?: number; dangerRate?: number },
): {
  level: "healthy" | "warning" | "danger" | "unknown";
  warningRate: number;
  dangerRate: number;
  text: string | null;
} {
  const alert = stats.admitted_stability_alert;
  const warningRate = overrides?.warningRate ?? alert?.warning_rate ?? DEFAULT_WARNING_RATE;
  const dangerRate = overrides?.dangerRate ?? alert?.danger_rate ?? DEFAULT_DANGER_RATE;
  const rate = stats.admitted_stability_24h_rate;
  const level = rate === null ? "unknown" : rate < dangerRate ? "danger" : rate < warningRate ? "warning" : "healthy";

  if (rate === null || level === "unknown" || level === "healthy") {
    return {
      level,
      warningRate,
      dangerRate,
      text: null,
    };
  }

  const rateText = `${(rate * 100).toFixed(1)}%`;
  if (level === "danger") {
    return {
      level,
      warningRate,
      dangerRate,
      text: `🚨 24h 稳定率进入告警区（当前 ${rateText}，告警线 ${(dangerRate * 100).toFixed(1)}%）。`,
    };
  }

  return {
    level,
    warningRate,
    dangerRate,
    text: `⚠ 24h 稳定率低于健康线（当前 ${rateText}，告警线 ${(dangerRate * 100).toFixed(1)}%，健康线 ${(warningRate * 100).toFixed(1)}%）。`,
  };
}

function describeHistorySource(source: GoalAdmissionConfigHistoryEntry["source"]): string {
  if (source === "rollback") {
    return "回滚";
  }
  if (source === "api_update") {
    return "更新";
  }
  if (source === "bootstrap") {
    return "初始化";
  }
  return source;
}

function formatHistoryTime(value: string): string {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return parsed.toLocaleString("zh-CN", { hour12: false });
}

export function GoalsAdmissionOverview({
  stats,
  history = [],
  onUpdateStabilityThresholds,
  onRollbackStabilityThresholds,
}: GoalsAdmissionOverviewProps) {
  const [warningDraft, setWarningDraft] = useState<number>(Math.round(DEFAULT_WARNING_RATE * 100));
  const [dangerDraft, setDangerDraft] = useState<number>(Math.round(DEFAULT_DANGER_RATE * 100));
  const [savingThresholds, setSavingThresholds] = useState(false);
  const [rollingBackThresholds, setRollingBackThresholds] = useState(false);
  const [thresholdError, setThresholdError] = useState<string | null>(null);
  const [thresholdOk, setThresholdOk] = useState<string | null>(null);
  const [pendingThresholdChange, setPendingThresholdChange] = useState<{
    previous: { warningRate: number; dangerRate: number };
    next: { warningRate: number; dangerRate: number };
    remainingMs: number;
  } | null>(null);
  const commitTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const countdownTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  function clearPendingTimers() {
    if (commitTimerRef.current) {
      clearTimeout(commitTimerRef.current);
      commitTimerRef.current = null;
    }
    if (countdownTimerRef.current) {
      clearInterval(countdownTimerRef.current);
      countdownTimerRef.current = null;
    }
  }

  useEffect(() => {
    if (!stats || pendingThresholdChange) {
      return;
    }
    const warning = stats.admitted_stability_alert?.warning_rate ?? DEFAULT_WARNING_RATE;
    const danger = stats.admitted_stability_alert?.danger_rate ?? DEFAULT_DANGER_RATE;
    setWarningDraft(Math.round(warning * 100));
    setDangerDraft(Math.round(danger * 100));
  }, [
    pendingThresholdChange,
    stats?.admitted_stability_alert?.warning_rate,
    stats?.admitted_stability_alert?.danger_rate,
  ]);

  useEffect(() => {
    return () => {
      clearPendingTimers();
    };
  }, []);

  if (!stats) {
    return null;
  }
  const stability = stats.admitted_stability_24h;
  const stabilityRate = describeStabilityRate(stats.admitted_stability_24h_rate);
  const serverWarningRate = stats.admitted_stability_alert?.warning_rate ?? DEFAULT_WARNING_RATE;
  const serverDangerRate = stats.admitted_stability_alert?.danger_rate ?? DEFAULT_DANGER_RATE;
  const effectiveWarningRate = pendingThresholdChange?.next.warningRate ?? serverWarningRate;
  const effectiveDangerRate = pendingThresholdChange?.next.dangerRate ?? serverDangerRate;
  const stabilityAlert = buildStabilityAlert(stats, {
    warningRate: effectiveWarningRate,
    dangerRate: effectiveDangerRate,
  });
  const canRollback = history.length >= 2;

  async function saveThresholds() {
    if (!onUpdateStabilityThresholds || savingThresholds || pendingThresholdChange) {
      return;
    }
    const warning = Math.max(0, Math.min(100, warningDraft)) / 100;
    const danger = Math.max(0, Math.min(100, dangerDraft)) / 100;
    if (danger > warning) {
      setThresholdError("告警线不能高于健康线。");
      setThresholdOk(null);
      return;
    }
    setThresholdError(null);
    setThresholdOk("已暂存，可在 5 秒内撤销");
    const previous = {
      warningRate: serverWarningRate,
      dangerRate: serverDangerRate,
    };
    const next = { warningRate: warning, dangerRate: danger };
    setPendingThresholdChange({
      previous,
      next,
      remainingMs: UNDO_WINDOW_MS,
    });
    clearPendingTimers();

    countdownTimerRef.current = setInterval(() => {
      setPendingThresholdChange((current) => {
        if (!current) {
          return current;
        }
        return {
          ...current,
          remainingMs: Math.max(0, current.remainingMs - 200),
        };
      });
    }, 200);

    commitTimerRef.current = setTimeout(async () => {
      setSavingThresholds(true);
      try {
        await onUpdateStabilityThresholds({
          stability_warning_rate: next.warningRate,
          stability_danger_rate: next.dangerRate,
        });
        setThresholdOk("阈值已保存");
      } catch (error) {
        setWarningDraft(Math.round(previous.warningRate * 100));
        setDangerDraft(Math.round(previous.dangerRate * 100));
        setThresholdError(error instanceof Error ? error.message : "阈值保存失败");
      } finally {
        clearPendingTimers();
        setPendingThresholdChange(null);
        setSavingThresholds(false);
      }
    }, UNDO_WINDOW_MS);
  }

  function undoThresholdChange() {
    if (!pendingThresholdChange) {
      return;
    }
    clearPendingTimers();
    setWarningDraft(Math.round(pendingThresholdChange.previous.warningRate * 100));
    setDangerDraft(Math.round(pendingThresholdChange.previous.dangerRate * 100));
    setPendingThresholdChange(null);
    setThresholdError(null);
    setThresholdOk("已撤销阈值变更");
  }

  async function rollbackThresholds() {
    if (!onRollbackStabilityThresholds || savingThresholds || rollingBackThresholds || pendingThresholdChange) {
      return;
    }
    setThresholdError(null);
    setThresholdOk(null);
    setRollingBackThresholds(true);
    try {
      await onRollbackStabilityThresholds();
      setThresholdOk("已回滚到上一版阈值");
    } catch (error) {
      setThresholdError(error instanceof Error ? error.message : "阈值回滚失败");
    } finally {
      setRollingBackThresholds(false);
    }
  }

  return (
    <section className="goals-admission" aria-label="目标准入守门">
      <div className="goals-admission__header">
        <span className="goals-admission__title">目标准入守门</span>
        <span className="goals-admission__hint">{describeMode(stats.mode)}</span>
      </div>
      {stabilityAlert.text ? (
        <div className={`goals-admission__alert goals-admission__alert--${stabilityAlert.level}`}>{stabilityAlert.text}</div>
      ) : null}

      <div className="goals-admission__metrics">
        <MetricCard label="今日通过" value={stats.today.admit} tone="success" />
        <MetricCard label="今日延后" value={stats.today.defer} tone="warning" />
        <MetricCard label="今日丢弃" value={stats.today.drop} tone="danger" />
        <MetricCard label="延后队列" value={stats.deferred_queue_size} tone="info" />
      </div>

      <div className="goals-admission__details">
        <SurfaceCard>
          <div className="goals-admission__detail-title">当前负载</div>
          <div className="goals-admission__detail-text">
            {`当前并行上限 ${stats.wip_limit} 个目标，今天已有 ${stats.today.wip_blocked} 次因 WIP 满载被延后。`}
          </div>
        </SurfaceCard>

        <SurfaceCard>
          <div className="goals-admission__detail-title">准入阈值</div>
          <div className="goals-admission__detail-list">
            <div className="goals-admission__detail-text">
              {formatThreshold("用户话题", stats.thresholds.user_topic.min_score, stats.thresholds.user_topic.defer_score)}
            </div>
            <div className="goals-admission__detail-text">
              {formatThreshold("链式续推", stats.thresholds.chain_next.min_score, stats.thresholds.chain_next.defer_score)}
            </div>
          </div>
        </SurfaceCard>

        <SurfaceCard>
          <div className="goals-admission__detail-title">转正后 24h 稳定性</div>
          <div className="goals-admission__detail-text">
            {`稳定 ${stability.stable}，再次延后 ${stability.re_deferred}，再次拦截 ${stability.dropped}。`}
          </div>
          <div className={`goals-admission__detail-text goals-admission__detail-text--${stabilityRate.tone}`}>
            {stabilityRate.text}
          </div>
          {pendingThresholdChange ? (
            <div className="goals-admission__pending">
              <span>{`阈值将在 ${Math.ceil(pendingThresholdChange.remainingMs / 1000)} 秒后生效。`}</span>
              <button
                type="button"
                className="btn btn--secondary btn--sm"
                onClick={undoThresholdChange}
              >
                撤销
              </button>
            </div>
          ) : null}
          <div className="goals-admission__threshold-editor">
            <label className="goals-admission__threshold-field">
              <span>健康线(%)</span>
              <input
                type="number"
                min={0}
                max={100}
                value={warningDraft}
                onChange={(event) => setWarningDraft(Number(event.target.value || 0))}
              />
            </label>
            <label className="goals-admission__threshold-field">
              <span>告警线(%)</span>
              <input
                type="number"
                min={0}
                max={100}
                value={dangerDraft}
                onChange={(event) => setDangerDraft(Number(event.target.value || 0))}
              />
            </label>
            <button
              type="button"
              className="btn btn--secondary btn--sm"
              onClick={saveThresholds}
              disabled={savingThresholds || pendingThresholdChange !== null || !onUpdateStabilityThresholds}
            >
              保存阈值
            </button>
            <button
              type="button"
              className="btn btn--secondary btn--sm"
              onClick={rollbackThresholds}
              disabled={
                savingThresholds
                || rollingBackThresholds
                || pendingThresholdChange !== null
                || !onRollbackStabilityThresholds
                || !canRollback
              }
            >
              回滚上一版
            </button>
          </div>
          {thresholdOk ? <div className="goals-admission__detail-text goals-admission__detail-text--success">{thresholdOk}</div> : null}
          {thresholdError ? (
            <div className="goals-admission__detail-text goals-admission__detail-text--danger">{thresholdError}</div>
          ) : null}
          {history.length > 0 ? (
            <div className="goals-admission__history">
              <div className="goals-admission__detail-title">阈值变更记录</div>
              {history.slice(0, 3).map((entry) => (
                <div
                  key={`${entry.revision}-${entry.created_at}`}
                  className="goals-admission__detail-text goals-admission__detail-text--muted"
                >
                  {`r${entry.revision} · ${describeHistorySource(entry.source)} · 健康 ${(entry.stability_warning_rate * 100).toFixed(0)}% / 告警 ${(entry.stability_danger_rate * 100).toFixed(0)}% · ${formatHistoryTime(entry.created_at)}${entry.rolled_back_from_revision ? `（回滚自 r${entry.rolled_back_from_revision}）` : ""}`}
                </div>
              ))}
            </div>
          ) : null}
        </SurfaceCard>
      </div>
    </section>
  );
}
