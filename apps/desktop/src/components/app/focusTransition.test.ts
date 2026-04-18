import { describe, expect, it } from "vitest";

import type { BeingState } from "../../lib/api";
import { deriveFocusTransitionHint, shouldRefreshFocusTransitionHint } from "./focusTransition";

function buildState(overrides: Partial<BeingState> = {}): BeingState {
  return {
    mode: "awake",
    focus_mode: "autonomy",
    current_thought: null,
    active_goal_ids: [],
    today_plan: null,
    last_action: null,
    ...overrides,
  };
}

describe("focusTransition", () => {
  it("explains when focus shifts to a user-triggered goal", () => {
    const previousState = buildState({
      focus_context: {
        goal_title: "收住今天这条线",
        source_kind: "today_plan_retained",
        source_label: "今天这条还留在眼前的计划",
        reason_kind: "today_plan_pending",
        reason_label: "今天这条还剩 1 步没做完",
        prompt_summary: "",
      },
    });
    const nextState = buildState({
      focus_context: {
        goal_title: "整理今天的对话记忆",
        source_kind: "user_topic_goal",
        source_label: "刚接住你这轮话题的事",
        reason_kind: "today_plan_pending",
        reason_label: "今天这条还剩 2 步没做完",
        prompt_summary: "",
      },
    });

    expect(shouldRefreshFocusTransitionHint(previousState, nextState)).toBe(true);
    expect(deriveFocusTransitionHint(previousState, nextState)).toBe(
      "焦点刚切到「整理今天的对话记忆」，因为它直接接住了你刚才这轮话题。",
    );
  });

  it("explains why the same focus is still being continued when the reason changes", () => {
    const previousState = buildState({
      focus_context: {
        goal_title: "整理今天的对话记忆",
        source_kind: "goal_chain",
        source_label: "她一直接着往下推进的这条线",
        reason_kind: "goal_chain_continuing",
        reason_label: "这条线已经推到第2步了，还会继续往下走",
        prompt_summary: "",
      },
    });
    const nextState = buildState({
      focus_context: {
        goal_title: "整理今天的对话记忆",
        source_kind: "goal_chain",
        source_label: "她一直接着往下推进的这条线",
        reason_kind: "goal_chain_closing",
        reason_label: "这条线已经推到第3步了，现在主要是在收尾",
        prompt_summary: "",
      },
    });

    expect(shouldRefreshFocusTransitionHint(previousState, nextState)).toBe(true);
    expect(deriveFocusTransitionHint(previousState, nextState)).toBe(
      "还在继续「整理今天的对话记忆」，因为这条线已经推到第3步了，现在主要是在收尾。",
    );
  });

  it("stays quiet when focus context does not materially change", () => {
    const state = buildState({
      focus_context: {
        goal_title: "整理今天的对话记忆",
        source_kind: "goal_chain",
        source_label: "她一直接着往下推进的这条线",
        reason_kind: "goal_chain_continuing",
        reason_label: "这条线已经推到第2步了，还会继续往下走",
        prompt_summary: "",
      },
    });

    expect(shouldRefreshFocusTransitionHint(state, state)).toBe(false);
    expect(deriveFocusTransitionHint(state, state)).toBeNull();
  });
});
