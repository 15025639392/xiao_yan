import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const {
  fetchGoals,
  fetchMessages,
  fetchState,
  fetchWorld,
  sleep,
  updateGoalStatus,
  wake,
} = vi.hoisted(() => ({
  fetchGoals: vi.fn(),
  fetchMessages: vi.fn(),
  fetchState: vi.fn(),
  fetchWorld: vi.fn(),
  sleep: vi.fn(),
  updateGoalStatus: vi.fn(),
  wake: vi.fn(),
}));

vi.mock("../../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../../lib/api")>("../../lib/api");
  return {
    ...actual,
    fetchGoals,
    fetchMessages,
    fetchState,
    fetchWorld,
    sleep,
    updateGoalStatus,
    wake,
  };
});

import { useAppStateMutations } from "./useAppStateMutations";

describe("useAppStateMutations", () => {
  beforeEach(() => {
    fetchGoals.mockReset();
    fetchMessages.mockReset();
    fetchState.mockReset();
    fetchWorld.mockReset();
    sleep.mockReset();
    updateGoalStatus.mockReset();
    wake.mockReset();
  });

  it("updates goal status and refreshes state", async () => {
    updateGoalStatus.mockResolvedValue({
      id: "goal-1",
      title: "整理今天的对话记忆",
      status: "completed",
    });
    fetchState.mockResolvedValue({
      mode: "awake",
      focus_mode: "autonomy",
      current_thought: null,
      active_goal_ids: [],
      today_plan: null,
      last_action: null,
    });

    const setError = vi.fn();
    const setGoals = vi.fn((updater) =>
      updater([{ id: "goal-1", title: "整理今天的对话记忆", status: "active" }]),
    );
    const setState = vi.fn();
    const updateFocusTransitionHint = vi.fn();

    const { result } = renderHook(() =>
      useAppStateMutations({
        setError,
        setGoals,
        setMessages: vi.fn(),
        setState,
        setWorld: vi.fn(),
        updateFocusTransitionHint,
      }),
    );

    await act(async () => {
      await result.current.handleUpdateGoalStatus("goal-1", "completed");
    });

    expect(updateGoalStatus).toHaveBeenCalledWith("goal-1", "completed");
    expect(fetchState).toHaveBeenCalled();
    expect(updateFocusTransitionHint).toHaveBeenCalled();
    expect(setState).toHaveBeenCalled();
  });

  it("refreshes persona-related app state together", async () => {
    fetchState.mockResolvedValue({
      mode: "awake",
      focus_mode: "autonomy",
      current_thought: null,
      active_goal_ids: [],
      today_plan: null,
      last_action: null,
    });
    fetchMessages.mockResolvedValue({
      messages: [
        { id: "user-1", role: "user", content: "你好" },
        { id: "assistant-1", role: "assistant", content: "我在。" },
      ],
    });
    fetchGoals.mockResolvedValue({
      goals: [{ id: "goal-1", title: "整理今天的对话记忆", status: "active" }],
    });
    fetchWorld.mockResolvedValue(null);

    const setMessages = vi.fn();
    const setGoals = vi.fn();
    const setWorld = vi.fn();
    const setState = vi.fn();
    const setError = vi.fn();
    const updateFocusTransitionHint = vi.fn();

    const { result } = renderHook(() =>
      useAppStateMutations({
        setError,
        setGoals,
        setMessages,
        setState,
        setWorld,
        updateFocusTransitionHint,
      }),
    );

    await act(async () => {
      await result.current.handlePersonaUpdated();
    });

    expect(fetchMessages).toHaveBeenCalled();
    expect(fetchGoals).toHaveBeenCalled();
    expect(fetchWorld).toHaveBeenCalled();
    expect(updateFocusTransitionHint).toHaveBeenCalled();
    expect(setState).toHaveBeenCalled();
    expect(setMessages).toHaveBeenCalled();
    expect(setGoals).toHaveBeenCalledWith([{ id: "goal-1", title: "整理今天的对话记忆", status: "active" }]);
    expect(setWorld).toHaveBeenCalledWith(null);
    expect(setError).toHaveBeenCalledWith("");
  });
});
