import type { Goal, TaskExecution, TaskExecutionStats } from "../../lib/api";
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
        <StatCard label="总任务数" value={executionStats.total_tasks} />
        <StatCard label="已完成" value={executionStats.completed} color="success" />
        <StatCard label="失败" value={executionStats.failed} color="danger" />
        <StatCard label="活跃中" value={executionStats.active} color="info" />
        <StatCard
          label="成功率"
          value={`${executionStats.success_rate.toFixed(1)}%`}
          color={
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

function StatCard({
  label,
  value,
  color = "default",
}: {
  label: string;
  value: number | string;
  color?: string;
}) {
  const colorVar =
    color === "success"
      ? "var(--success)"
      : color === "danger"
        ? "var(--danger)"
        : color === "warning"
          ? "var(--warning)"
          : color === "info"
            ? "var(--info)"
            : "var(--text-primary)";
  return (
    <div
      style={{
        padding: "var(--space-3)",
        background: "var(--bg-surface-elevated)",
        borderRadius: "var(--radius-md)",
        border: "1px solid var(--border-default)",
      }}
    >
      <div style={{ fontSize: "0.75rem", color: "var(--text-tertiary)", marginBottom: "var(--space-1)" }}>
        {label}
      </div>
      <div style={{ fontSize: "1.5rem", fontWeight: 600, color: colorVar }}>{value}</div>
    </div>
  );
}

function ExecutionCard({ execution, allGoals }: { execution: TaskExecution; allGoals: Goal[] }) {
  const goal = allGoals.find((g) => g.id === execution.goal_id);

  return (
    <div
      style={{
        padding: "var(--space-3)",
        background: "var(--bg-surface-elevated)",
        borderRadius: "var(--radius-md)",
        border: "1px solid var(--border-default)",
      }}
    >
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
        <span>{new Date(execution.started_at).toLocaleString("zh-CN")}</span>
      </div>
    </div>
  );
}

