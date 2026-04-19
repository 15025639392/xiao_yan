import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const {
  fetchMessages,
  fetchState,
  sleep,
  wake,
} = vi.hoisted(() => ({
  fetchMessages: vi.fn(),
  fetchState: vi.fn(),
  sleep: vi.fn(),
  wake: vi.fn(),
}));

vi.mock("../../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../../lib/api")>("../../lib/api");
  return {
    ...actual,
    fetchMessages,
    fetchState,
    sleep,
    wake,
  };
});

import { useAppStateMutations } from "./useAppStateMutations";

describe("useAppStateMutations", () => {
  beforeEach(() => {
    fetchMessages.mockReset();
    fetchState.mockReset();
    sleep.mockReset();
    wake.mockReset();
  });

  it("refreshes persona-related app state together", async () => {
    fetchState.mockResolvedValue({
      mode: "awake",
      focus_mode: "autonomy",
      current_thought: null,
      last_action: null,
    });
    fetchMessages.mockResolvedValue({
      messages: [
        { id: "user-1", role: "user", content: "你好" },
        { id: "assistant-1", role: "assistant", content: "我在。" },
      ],
    });

    const setMessages = vi.fn();
    const setState = vi.fn();
    const setError = vi.fn();
    const { result } = renderHook(() =>
      useAppStateMutations({
        setError,
        setMessages,
        setState,
      }),
    );

    await act(async () => {
      await result.current.handlePersonaUpdated();
    });

    expect(fetchMessages).toHaveBeenCalled();
    expect(setState).toHaveBeenCalled();
    expect(setMessages).toHaveBeenCalled();
    expect(setError).toHaveBeenCalledWith("");
  });
});
