import { renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { BeingState } from "../../lib/api";
import { useFocusPresentation } from "./useFocusPresentation";

function buildState(overrides: Partial<BeingState> = {}): BeingState {
  return {
    mode: "awake",
    focus_mode: "autonomy",
    current_thought: null,
    last_action: null,
    ...overrides,
  };
}

describe("useFocusPresentation", () => {
  it("prefers focus subject title before the active goal", () => {
    const state = buildState({
      focus_subject: {
        kind: "lingering",
        title: "你刚才说最近提不起劲",
        why_now: "这句话虽然还没整理成目标，但我心里还挂着。",
      },
    });

    const { result } = renderHook(() => useFocusPresentation(state));

    expect(result.current.focusGoalTitle).toBe("你刚才说最近提不起劲");
  });

  it("does not resolve focus title from the active goal or legacy plan anymore", () => {
    const state = buildState({
    });

    const { result } = renderHook(() => useFocusPresentation(state));

    expect(result.current.focusGoalTitle).toBeNull();
  });

  it("exposes focus context when present", () => {
    const state = buildState({
      focus_context: {
        goal_title: "整理今天的对话记忆",
        source_kind: "user_topic_goal",
        source_label: "刚接住你这轮话题的事",
        reason_kind: "focus_subject_reason",
        reason_label: "今天这条还剩 2 步没做完",
        prompt_summary: "当前焦点来自刚接住你这轮话题的事。",
      },
    });

    const { result } = renderHook(() => useFocusPresentation(state));

    expect(result.current.focusContext?.prompt_summary).toBe("当前焦点来自刚接住你这轮话题的事。");
  });
});
