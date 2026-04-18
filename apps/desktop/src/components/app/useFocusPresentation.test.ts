import { act, renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { BeingState, Goal } from "../../lib/api";
import { useFocusPresentation } from "./useFocusPresentation";

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

describe("useFocusPresentation", () => {
  it("resolves focus title from the active goal first", () => {
    const state = buildState({
      active_goal_ids: ["goal-1"],
      today_plan: {
        goal_id: "goal-2",
        goal_title: "计划里的备选焦点",
        steps: [],
      },
    });
    const goals: Goal[] = [
      {
        id: "goal-1",
        title: "当前真正焦点",
        status: "active",
        created_at: null,
        updated_at: null,
      },
    ];

    const { result } = renderHook(() => useFocusPresentation(state, goals));

    expect(result.current.focusGoalTitle).toBe("当前真正焦点");
  });

  it("updates focus transition hint when next state changes focus", () => {
    const initialState = buildState({
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

    const { result, rerender } = renderHook(
      ({ state }) => useFocusPresentation(state, []),
      { initialProps: { state: initialState } },
    );

    act(() => {
      result.current.updateFocusTransitionHint(nextState);
    });
    rerender({ state: nextState });

    expect(result.current.focusTransitionHint).toBe(
      "焦点刚切到「整理今天的对话记忆」，因为它直接接住了你刚才这轮话题。",
    );
  });
});
