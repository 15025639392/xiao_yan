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
    <section>
      <p>Mode: {state.mode}</p>
      <p>Phase: {renderFocusMode(state.focus_mode)}</p>
      {focusGoalTitle ? <p>Focus Goal: {focusGoalTitle}</p> : null}
      {state.last_action ? (
        <p>Last Action: {state.last_action.command} -&gt; {state.last_action.output}</p>
      ) : null}
      <p>Thought: {state.current_thought ?? "..."}</p>
      {state.today_plan ? (
        <section>
          <h2>她今天的计划</h2>
          <p>{state.today_plan.goal_title}</p>
          {planCompleted ? <p>今日计划已完成</p> : null}
          <ul>
            {state.today_plan.steps.map((step) => (
              <li key={step.content}>
                {step.status === "completed" ? "[done] " : "[todo] "}
                {step.content}
                {step.kind === "action" && step.command ? ` (${step.command})` : ""}
              </li>
            ))}
          </ul>
        </section>
      ) : null}
      {selfImprovementJob ? (
        <section>
          <h2>她刚刚为什么改自己</h2>
          <p>Area: {selfImprovementJob.target_area}</p>
          <p>Stage: {renderSelfImprovementStatus(selfImprovementJob.status)}</p>
          <p>Reason: {selfImprovementJob.reason}</p>
          <p>Spec: {selfImprovementJob.spec}</p>
          {selfImprovementJob.patch_summary ? (
            <p>Patch: {selfImprovementJob.patch_summary}</p>
          ) : null}
          {selfImprovementJob.red_verification ? (
            <>
              <p>
                Red Verification:{" "}
                {selfImprovementJob.red_verification.passed ? "passed" : "failed"}
              </p>
              {selfImprovementJob.red_verification.summary ? (
                <p>Red Summary: {selfImprovementJob.red_verification.summary}</p>
              ) : null}
            </>
          ) : null}
          {selfImprovementJob.verification ? (
            <>
              <p>
                Verification: {selfImprovementJob.verification.passed ? "passed" : "failed"}
              </p>
              {selfImprovementJob.verification.summary ? (
                <p>Verification Summary: {selfImprovementJob.verification.summary}</p>
              ) : null}
            </>
          ) : null}
          {selfImprovementJob.touched_files?.length ? (
            <p>Touched Files: {selfImprovementJob.touched_files.join(", ")}</p>
          ) : null}
        </section>
      ) : null}
      {error ? <p>{error}</p> : null}
    </section>
  );
}

function renderFocusMode(focusMode: BeingState["focus_mode"]): string {
  if (focusMode === "morning_plan") {
    return "她今天的计划";
  }
  if (focusMode === "autonomy") {
    return "常规自主";
  }
  if (focusMode === "self_improvement") {
    return "自我编程";
  }
  return "休眠";
}

function renderSelfImprovementStatus(
  status: NonNullable<BeingState["self_improvement_job"]>["status"],
): string {
  if (status === "diagnosing") {
    return "诊断中";
  }
  if (status === "patching") {
    return "写补丁";
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
