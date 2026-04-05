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
    <section className="panel panel--rail">
      <div className="panel__header">
        <div>
          <p className="panel__eyebrow">系统读数</p>
          <h2 className="panel__title">当前状态</h2>
        </div>
        <span className={`status-badge status-badge--${state.mode}`}>
          {renderModeLabel(state.mode)}
        </span>
      </div>
      <div className="metric-grid">
        <div className="metric-card">
          <p className="metric-card__label">在线状态</p>
          <p className="metric-card__value">{renderModeLabel(state.mode)}</p>
        </div>
        <div className="metric-card">
          <p className="metric-card__label">当前阶段</p>
          <p className="metric-card__value">{renderFocusMode(state.focus_mode)}</p>
        </div>
      </div>
      {focusGoalTitle ? (
        <div className="metric-card metric-card--wide">
          <p className="metric-card__label">当前专注目标</p>
          <p className="metric-card__value">{focusGoalTitle}</p>
        </div>
      ) : null}
      {state.last_action ? (
        <div className="metric-card metric-card--wide">
          <p className="metric-card__label">最近动作</p>
          <p className="metric-card__value">
            {state.last_action.command} -&gt; {state.last_action.output}
          </p>
        </div>
      ) : null}
      <section className="thought-card">
        <p className="thought-card__label">当前想法</p>
        <p className="thought-card__value">{state.current_thought ?? "还没有浮现新的念头。"}</p>
      </section>
      {state.today_plan ? (
        <section className="mini-panel">
          <div className="mini-panel__header">
            <h3>今日计划</h3>
            {planCompleted ? <span className="status-badge">今日计划已完成</span> : null}
          </div>
          <p className="mini-panel__lead">{state.today_plan.goal_title}</p>
          <ul className="plan-list">
            {state.today_plan.steps.map((step) => (
              <li key={step.content} className="plan-list__item">
                <span className={`plan-badge plan-badge--${step.status}`}>
                  {step.status === "completed" ? "已完成" : "待处理"}
                </span>
                <div className="plan-list__content">
                  <p>{step.content}</p>
                  {step.kind === "action" && step.command ? (
                    <p className="plan-list__command">{step.command}</p>
                  ) : null}
                </div>
              </li>
            ))}
          </ul>
        </section>
      ) : null}
      {selfImprovementJob ? (
        <section className="mini-panel">
          <div className="mini-panel__header">
            <h3>她刚刚为什么改自己</h3>
            <span className="status-badge">
              {renderSelfImprovementStatus(selfImprovementJob.status)}
            </span>
          </div>
          <div className="detail-list">
            <div>
              <p className="detail-list__label">目标区域</p>
              <p className="detail-list__value">{selfImprovementJob.target_area}</p>
            </div>
            <div>
              <p className="detail-list__label">当前阶段</p>
              <p className="detail-list__value">
                {renderSelfImprovementStatus(selfImprovementJob.status)}
              </p>
            </div>
          </div>
          <div className="detail-row">
            <p className="detail-list__label">原因</p>
            <p className="detail-list__value">{selfImprovementJob.reason}</p>
          </div>
          <div className="detail-row">
            <p className="detail-list__label">方案</p>
            <p className="detail-list__value">{selfImprovementJob.spec}</p>
          </div>
          {selfImprovementJob.patch_summary ? (
            <div className="detail-row">
              <p className="detail-list__label">补丁摘要</p>
              <p className="detail-list__value">{selfImprovementJob.patch_summary}</p>
            </div>
          ) : null}
          {selfImprovementJob.red_verification ? (
            <div className="detail-row">
              <p className="detail-list__label">红测验证</p>
              <p className="detail-list__value">
                {selfImprovementJob.red_verification.passed ? "通过" : "失败"}
              </p>
              {selfImprovementJob.red_verification.summary ? (
                <p className="detail-list__meta">{selfImprovementJob.red_verification.summary}</p>
              ) : null}
            </div>
          ) : null}
          {selfImprovementJob.verification ? (
            <div className="detail-row">
              <p className="detail-list__label">最终验证</p>
              <p className="detail-list__value">
                {selfImprovementJob.verification.passed ? "通过" : "失败"}
              </p>
              {selfImprovementJob.verification.summary ? (
                <p className="detail-list__meta">{selfImprovementJob.verification.summary}</p>
              ) : null}
            </div>
          ) : null}
          {selfImprovementJob.touched_files?.length ? (
            <div className="detail-row">
              <p className="detail-list__label">变更文件</p>
              <p className="detail-list__value">{selfImprovementJob.touched_files.join(", ")}</p>
            </div>
          ) : null}
        </section>
      ) : null}
      {error ? <p className="error-banner">{error}</p> : null}
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
