import type { Goal } from "../../lib/api";

export type GoalAdmissionDisplay = {
  badge: string;
  summary: string;
  scoreText: string;
  trajectoryText: string | null;
  tone: "admit" | "defer" | "drop";
};

function explainReason(goal: Goal): string {
  const reason = goal.admission?.reason ?? "";
  if (reason === "user_score") {
    return "符合用户话题准入阈值，已允许进入目标看板。";
  }
  if (reason === "world_score") {
    return "符合世界事件准入阈值，已允许进入目标看板。";
  }
  if (reason === "chain_score") {
    return "符合链式续推准入阈值，这条线可以继续往前。";
  }
  if (reason === "wip_full") {
    return "原本可推进，但当前并行负载已满，应该进入延后观察。";
  }
  if (reason.startsWith("relationship_boundary:")) {
    return "命中了关系边界，理论上不该进入目标看板。";
  }
  return `当前准入依据：${reason}`;
}

export function getGoalAdmissionDisplay(goal: Goal): GoalAdmissionDisplay | null {
  if (!goal.admission) {
    return null;
  }

  const tone = goal.admission.applied_decision;
  const badge = tone === "admit" ? "准入通过" : tone === "defer" ? "延后观察" : "边界拦截";
  const retries = Math.max(goal.admission.deferred_retries ?? 0, 0);

  return {
    badge,
    summary: explainReason(goal),
    scoreText: `评分 ${goal.admission.score.toFixed(2)}`,
    trajectoryText: tone === "admit" && retries > 0 ? `延后 ${retries} 次后转正` : null,
    tone,
  };
}
