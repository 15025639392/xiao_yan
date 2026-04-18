import type { FocusEffort } from "./api";

export function getFocusEffortTitle(focusEffort?: FocusEffort | null): string | null {
  if (!focusEffort) {
    return null;
  }

  if (focusEffort.action_kind === "command" || focusEffort.action_kind === "plan_action") {
    return "刚刚为焦点执行了动作";
  }
  if (focusEffort.action_kind === "plan_step") {
    return "刚刚推进了一步";
  }
  if (focusEffort.action_kind === "goal_completed") {
    return "刚刚确认了这条线的收尾";
  }
  if (focusEffort.action_kind === "chain_advanced") {
    return "刚刚把这条线接到了下一步";
  }
  if (focusEffort.action_kind === "chat_reply") {
    return "刚刚围绕它回应了你";
  }
  return "刚刚围绕焦点做了这件事";
}

export function getFocusEffortLines(focusEffort?: FocusEffort | null): string[] {
  if (!focusEffort) {
    return [];
  }

  return [
    `为什么现在做: ${focusEffort.why_now}`,
    `刚刚做了什么: ${focusEffort.did_what}`,
    focusEffort.effect ? `产生了什么变化: ${focusEffort.effect}` : null,
    focusEffort.next_hint ? `接下来可能怎么走: ${focusEffort.next_hint}` : null,
  ].filter((value): value is string => Boolean(value));
}
