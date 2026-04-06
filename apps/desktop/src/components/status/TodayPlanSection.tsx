import type { BeingState } from "../../lib/api";
import { StatusBadge } from "../ui";

type TodayPlan = NonNullable<BeingState["today_plan"]>;

type TodayPlanSectionProps = {
  plan: TodayPlan;
  planCompleted: boolean;
};

export function TodayPlanSection({ plan, planCompleted }: TodayPlanSectionProps) {
  return (
    <section style={{ marginTop: "var(--space-5)" }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "var(--space-3)" }}>
        <h3 style={{ margin: 0, fontSize: "0.875rem", fontWeight: 600 }}>今日计划</h3>
        {planCompleted ? <StatusBadge tone="completed">已完成</StatusBadge> : null}
      </div>
      <p style={{ margin: "0 0 var(--space-3)", color: "var(--text-secondary)", fontSize: "0.875rem" }}>
        {plan.goal_title}
      </p>
      <ul style={{ margin: 0, padding: 0, listStyle: "none", display: "flex", flexDirection: "column", gap: "var(--space-2)" }}>
        {plan.steps.map((step) => (
          <li
            key={step.content}
            style={{
              display: "flex",
              gap: "var(--space-3)",
              alignItems: "flex-start",
              padding: "var(--space-3)",
              background: "var(--bg-surface-elevated)",
              borderRadius: "var(--radius-md)",
            }}
          >
            <span
              style={{
                padding: "var(--space-1) var(--space-2)",
                background: step.status === "completed" ? "var(--success-muted)" : "var(--warning-muted)",
                color: step.status === "completed" ? "var(--success)" : "var(--warning)",
                borderRadius: "var(--radius-full)",
                fontSize: "0.75rem",
                fontWeight: 500,
                flexShrink: 0,
              }}
            >
              {step.status === "completed" ? "已完成" : "待处理"}
            </span>
            <div>
              <p style={{ margin: 0, fontSize: "0.875rem" }}>{step.content}</p>
              {step.kind === "action" && step.command ? (
                <p style={{ margin: "var(--space-1) 0 0", fontSize: "0.75rem", color: "var(--text-tertiary)", fontFamily: "monospace" }}>
                  {step.command}
                </p>
              ) : null}
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
