import type { Goal } from "../../lib/api";

export type GoalSourceMeta = {
  label: string;
  summary: string;
  contextLabel: string;
  context: string | null;
  tone: "user" | "world" | "chain" | "manual";
};

export function getGoalSourceMeta(goal: Goal): GoalSourceMeta {
  if (goal.parent_goal_id || (goal.generation ?? 0) > 0 || goal.title.startsWith("继续推进：")) {
    return {
      label: "链式续推",
      summary: "不是全新目标，而是沿着上一代目标继续往前推进。",
      contextLabel: "承接线索",
      context: goal.source ?? null,
      tone: "chain",
    };
  }

  if (goal.title.startsWith("持续理解用户最近在意的话题：")) {
    return {
      label: "用户话题",
      summary: "来自最近一次用户表达或关注。",
      contextLabel: "用户线索",
      context: goal.source ?? null,
      tone: "user",
    };
  }

  if (goal.title.startsWith("继续消化自己刚经历的状态：")) {
    return {
      label: "世界事件",
      summary: "来自她刚经历的一次世界或内在事件。",
      contextLabel: "事件线索",
      context: goal.source ?? null,
      tone: "world",
    };
  }

  return {
    label: "手动设定",
    summary: "这是当前直接录入或保留下来的目标。",
    contextLabel: "补充线索",
    context: goal.source ?? null,
    tone: "manual",
  };
}
