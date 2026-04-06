import type { InnerWorldState } from "../../lib/api";

export function renderTimeOfDay(timeOfDay: InnerWorldState["time_of_day"]): string {
  if (timeOfDay === "morning") return "早晨";
  if (timeOfDay === "afternoon") return "下午";
  if (timeOfDay === "evening") return "傍晚";
  return "夜晚";
}

export function renderScale(value: "low" | "medium" | "high"): string {
  if (value === "low") return "低";
  if (value === "medium") return "中等";
  return "高";
}

export function renderMood(mood: InnerWorldState["mood"]): string {
  if (mood === "calm") return "平静";
  if (mood === "engaged") return "投入";
  return "疲惫";
}

export function renderFocusStage(stage: Exclude<InnerWorldState["focus_stage"], "none" | undefined>): string {
  if (stage === "start") return "启动中";
  if (stage === "deepen") return "深入中";
  return "收束中";
}
