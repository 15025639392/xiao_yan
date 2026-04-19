import type { FocusContext } from "./api";

export type FocusContextBadge = {
  label: string;
  tone: string;
};

export function getFocusTransitionHint(
  previousFocusContext?: FocusContext | null,
  nextFocusContext?: FocusContext | null,
): string | null {
  if (!nextFocusContext) {
    return null;
  }

  if (!previousFocusContext) {
    return `现在先把重心放在「${nextFocusContext.goal_title}」。`;
  }

  if (previousFocusContext.goal_title === nextFocusContext.goal_title) {
    if (
      previousFocusContext.reason_kind !== nextFocusContext.reason_kind &&
      nextFocusContext.reason_label.trim().length > 0
    ) {
      return `还在继续「${nextFocusContext.goal_title}」，因为${nextFocusContext.reason_label}。`;
    }
    return null;
  }

  if (nextFocusContext.source_kind === "user_topic_goal") {
    return `焦点刚切到「${nextFocusContext.goal_title}」，因为它直接接住了你刚才这轮话题。`;
  }
  if (nextFocusContext.source_kind === "user_topic_focus") {
    return `焦点先落在「${nextFocusContext.goal_title}」，因为你刚才这轮话题还在牵动她。`;
  }
  if (nextFocusContext.source_kind === "goal_chain") {
    return `焦点转回「${nextFocusContext.goal_title}」，因为这条线还在续推。`;
  }
  if (nextFocusContext.source_kind === "lingering_focus") {
    return `焦点还停在「${nextFocusContext.goal_title}」，因为这件事虽然没在执行，但她心里还没放下。`;
  }
  if (nextFocusContext.source_kind === "deferred_goal_reactivated") {
    return `焦点回到「${nextFocusContext.goal_title}」，因为这件事从延后状态重新转回来了。`;
  }

  return `焦点切到「${nextFocusContext.goal_title}」，因为它现在仍是最在前面的活跃线索。`;
}

export function getFocusContextLines(focusContext?: FocusContext | null): string[] {
  if (!focusContext) {
    return [];
  }

  const summary = focusContext.prompt_summary.trim();
  const lines = [
    focusContext.source_label.trim().length > 0
      ? `会先盯着这件事，因为这是${focusContext.source_label}。`
      : null,
    focusContext.reason_label.trim().length > 0 ? `现在还在继续推进，因为${focusContext.reason_label}。` : null,
  ].filter((value): value is string => typeof value === "string" && value.trim().length > 0);

  if (lines.length > 0) {
    return lines;
  }

  if (summary.length > 0) {
    return [summary];
  }

  return [];
}

export function getFocusContextBadge(focusContext?: FocusContext | null): FocusContextBadge | null {
  const sourceKind = focusContext?.source_kind;
  if (sourceKind === "user_topic_goal") {
    return { label: "用户触发", tone: "active" };
  }
  if (sourceKind === "user_topic_focus") {
    return { label: "话题牵动", tone: "active" };
  }
  if (sourceKind === "goal_chain") {
    return { label: "续推中", tone: "completed" };
  }
  if (sourceKind === "lingering_focus") {
    return { label: "余波未落", tone: "paused" };
  }
  if (sourceKind === "deferred_goal_reactivated") {
    return { label: "重新转回", tone: "abandoned" };
  }
  if (sourceKind === "retained_goal" || sourceKind === "active_goal") {
    return { label: "当前活跃", tone: "active" };
  }
  return null;
}
