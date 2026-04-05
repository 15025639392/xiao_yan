import type { BeingState } from "../lib/api";

type StatusPanelProps = {
  state: BeingState;
  error: string;
  focusGoalTitle?: string | null;
};

export function StatusPanel({ state, error, focusGoalTitle }: StatusPanelProps) {
  const planCompleted =
    state.today_plan?.steps.length &&
    state.today_plan.steps.every((step) => step.status === "completed");
  const selfImprovementJob = state.self_improvement_job;

  return (
    <section className="panel">
      <div className="panel__header">
        <div className="panel__title-group">
          <div className="panel__icon">📊</div>
          <div>
            <h2 className="panel__title">当前状态</h2>
            <p className="panel__subtitle">系统实时读数</p>
          </div>
        </div>
        <span className={`status-badge status-badge--${state.mode}`}>
          {renderModeLabel(state.mode)}
        </span>
      </div>

      <div className="panel__content">
        <div className="metric-grid">
          <div className="metric-card">
            <p className="metric-card__label">运行状态</p>
            <p className="metric-card__value">{renderModeLabel(state.mode)}</p>
          </div>
          <div className="metric-card">
            <p className="metric-card__label">当前阶段</p>
            <p className="metric-card__value">{renderFocusMode(state.focus_mode)}</p>
          </div>
        </div>

        {focusGoalTitle ? (
          <div className="metric-card" style={{ marginTop: "var(--space-3)" }}>
            <p className="metric-card__label">当前专注目标</p>
            <p className="metric-card__value">{focusGoalTitle}</p>
          </div>
        ) : null}

        {state.last_action ? (
          <div className="metric-card" style={{ marginTop: "var(--space-3)" }}>
            <p className="metric-card__label">最近动作</p>
            <p className="metric-card__value">
              {state.last_action.command} → {state.last_action.output}
            </p>
          </div>
        ) : null}

        <div className="metric-card" style={{ marginTop: "var(--space-3)" }}>
          <p className="metric-card__label">当前想法</p>
          <p className="metric-card__value">{state.current_thought ?? "还没有浮现新的念头。"}</p>
        </div>

        {state.today_plan ? (
          <section style={{ marginTop: "var(--space-5)" }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "var(--space-3)" }}>
              <h3 style={{ margin: 0, fontSize: "0.875rem", fontWeight: 600 }}>今日计划</h3>
              {planCompleted ? <span className="status-badge status-badge--completed">已完成</span> : null}
            </div>
            <p style={{ margin: "0 0 var(--space-3)", color: "var(--text-secondary)", fontSize: "0.875rem" }}>
              {state.today_plan.goal_title}
            </p>
            <ul style={{ margin: 0, padding: 0, listStyle: "none", display: "flex", flexDirection: "column", gap: "var(--space-2)" }}>
              {state.today_plan.steps.map((step) => (
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
        ) : null}

        {selfImprovementJob ? (
          <section style={{ marginTop: "var(--space-5)" }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "var(--space-3)" }}>
              <h3 style={{ margin: 0, fontSize: "0.875rem", fontWeight: 600 }}>自我修复</h3>
              <span className="status-badge status-badge--active">
                {renderSelfImprovementStatus(selfImprovementJob.status)}
              </span>
            </div>
            <div className="metric-grid" style={{ marginBottom: "var(--space-3)" }}>
              <div className="metric-card">
                <p className="metric-card__label">目标区域</p>
                <p className="metric-card__value">{selfImprovementJob.target_area}</p>
              </div>
              <div className="metric-card">
                <p className="metric-card__label">当前阶段</p>
                <p className="metric-card__value">{renderSelfImprovementStatus(selfImprovementJob.status)}</p>
              </div>
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
              <div>
                <p style={{ margin: "0 0 var(--space-1)", fontSize: "0.75rem", color: "var(--text-tertiary)" }}>原因</p>
                <p style={{ margin: 0, fontSize: "0.875rem", color: "var(--text-secondary)" }}>{selfImprovementJob.reason}</p>
              </div>
              <div>
                <p style={{ margin: "0 0 var(--space-1)", fontSize: "0.75rem", color: "var(--text-tertiary)" }}>方案</p>
                <p style={{ margin: 0, fontSize: "0.875rem", color: "var(--text-secondary)" }}>{selfImprovementJob.spec}</p>
              </div>
              {selfImprovementJob.patch_summary ? (
                <div>
                  <p style={{ margin: "0 0 var(--space-1)", fontSize: "0.75rem", color: "var(--text-tertiary)" }}>补丁摘要</p>
                  <p style={{ margin: 0, fontSize: "0.875rem", color: "var(--text-secondary)" }}>{selfImprovementJob.patch_summary}</p>
                </div>
              ) : null}
            </div>
          </section>
        ) : null}

        {error ? (
          <div style={{ marginTop: "var(--space-4)", padding: "var(--space-3)", background: "var(--danger-muted)", borderRadius: "var(--radius-md)", color: "var(--danger)", fontSize: "0.875rem" }}>
            {error}
          </div>
        ) : null}
      </div>
    </section>
  );
}

function renderFocusMode(focusMode: BeingState["focus_mode"]): string {
  if (focusMode === "morning_plan") {
    return "晨间计划";
  }
  if (focusMode === "autonomy") {
    return "常规自主";
  }
  if (focusMode === "self_improvement") {
    return "自我修复";
  }
  return "休眠";
}

function renderModeLabel(mode: BeingState["mode"]): string {
  return mode === "awake" ? "运行中" : "休眠中";
}

function renderSelfImprovementStatus(
  status: NonNullable<BeingState["self_improvement_job"]>["status"],
): string {
  if (status === "diagnosing") {
    return "诊断中";
  }
  if (status === "patching") {
    return "修补中";
  }
  if (status === "verifying") {
    return "验证中";
  }
  if (status === "applied") {
    return "已生效";
  }
  if (status === "failed") {
    return "失败";
  }
  return "待开始";
}
