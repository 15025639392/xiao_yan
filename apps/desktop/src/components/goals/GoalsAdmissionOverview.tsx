import type { GoalAdmissionStats } from "../../lib/api";
import { MetricCard, SurfaceCard } from "../ui";

type GoalsAdmissionOverviewProps = {
  stats: GoalAdmissionStats | null;
};

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

export function GoalsAdmissionOverview({ stats }: GoalsAdmissionOverviewProps) {
  if (!stats) {
    return null;
  }
  const stability = stats.admitted_stability_24h;

  return (
    <section className="goals-admission" aria-label="目标准入守门">
      <div className="goals-admission__header">
        <span className="goals-admission__title">目标准入守门</span>
        <span className="goals-admission__hint">{describeMode(stats.mode)}</span>
      </div>

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
              {formatThreshold("世界事件", stats.thresholds.world_event.min_score, stats.thresholds.world_event.defer_score)}
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
        </SurfaceCard>
      </div>
    </section>
  );
}
