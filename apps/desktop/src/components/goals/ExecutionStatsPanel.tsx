import type { Goal, TaskExecution, TaskExecutionStats } from "../../lib/api";
import { formatDateTimeZh } from "../../lib/utils";
import { MetricCard, SurfaceCard } from "../ui";
import { renderGoalStatus } from "./goalsUtils";

type ExecutionStatsPanelProps = {
  executionStats: TaskExecutionStats;
  activeExecutions: TaskExecution[];
  goals: Goal[];
};

export function ExecutionStatsPanel({ executionStats, activeExecutions, goals }: ExecutionStatsPanelProps) {
  return (
    <section style={{ marginBottom: "var(--space-5)" }}>
      <h3 style={{ margin: "0 0 var(--space-3)", fontSize: "0.875rem", fontWeight: 600 }}>任务执行统计</h3>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "var(--space-3)" }}>
        <MetricCard label="总任务数" value={executionStats.total_tasks} />
        <MetricCard label="已完成" value={executionStats.completed} tone="success" />
        <MetricCard label="失败" value={executionStats.failed} tone="danger" />
        <MetricCard label="活跃中" value={executionStats.active} tone="info" />
        <MetricCard
          label="成功率"
          value={`${executionStats.success_rate.toFixed(1)}%`}
          tone={
            executionStats.success_rate >= 80
              ? "success"
              : executionStats.success_rate >= 50
                ? "warning"
                : "danger"
          }
        />
      </div>

      {activeExecutions.length > 0 ? (
        <div style={{ marginTop: "var(--space-4)" }}>
          <h4 style={{ margin: "0 0 var(--space-2)", fontSize: "0.8125rem", color: "var(--text-secondary)" }}>
            活跃任务 ({activeExecutions.length})
          </h4>
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)" }}>
            {activeExecutions.map((execution) => (
              <ExecutionCard key={execution.goal_id} execution={execution} allGoals={goals} />
            ))}
          </div>
        </div>
      ) : null}
    </section>
  );
}

function ExecutionCard({ execution, allGoals }: { execution: TaskExecution; allGoals: Goal[] }) {
  const goal = allGoals.find((g) => g.id === execution.goal_id);

  return (
    <SurfaceCard>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: "var(--space-2)",
        }}
      >
        <span style={{ fontSize: "0.875rem", fontWeight: 500 }}>{goal?.title || execution.goal_id}</span>
        <span
          className="intensity-badge"
          style={{ fontSize: "0.75rem", padding: "var(--space-1) var(--space-2)", borderRadius: "var(--radius-full)" }}
        >
          {(execution.progress * 100).toFixed(0)}%
        </span>
      </div>
      <div style={{ marginBottom: "var(--space-2)" }}>
        <div
          style={{
            height: "4px",
            background: "var(--bg-surface)",
            borderRadius: "var(--radius-full)",
            overflow: "hidden",
          }}
        >
          <div
            style={{
              height: "100%",
              background:
                execution.status === "completed"
                  ? "var(--success)"
                  : execution.status === "abandoned"
                    ? "var(--danger)"
                    : "var(--info)",
              borderRadius: "var(--radius-full)",
              transition: "width 300ms ease",
              width: `${execution.progress * 100}%`,
            }}
          />
        </div>
      </div>
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.75rem", color: "var(--text-tertiary)" }}>
        <span>{renderGoalStatus(execution.status)}</span>
        <span>{formatDateTimeZh(execution.started_at)}</span>
      </div>
    </SurfaceCard>
  );
}
