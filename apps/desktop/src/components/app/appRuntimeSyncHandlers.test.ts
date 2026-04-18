import { describe, expect, it, vi } from "vitest";

const {
  applyIncomingRuntimeEvent,
  getPersonaProfileFromRealtimeEvent,
} = vi.hoisted(() => ({
  applyIncomingRuntimeEvent: vi.fn(),
  getPersonaProfileFromRealtimeEvent: vi.fn(),
}));

const { applyIncomingChatEvent } = vi.hoisted(() => ({
  applyIncomingChatEvent: vi.fn(),
}));

vi.mock("./runtimeSync", async () => {
  const actual = await vi.importActual<typeof import("./runtimeSync")>("./runtimeSync");
  return {
    ...actual,
    applyIncomingRuntimeEvent,
    getPersonaProfileFromRealtimeEvent,
  };
});

vi.mock("./chatSync", () => ({
  applyIncomingChatEvent,
}));

import {
  applyInitialRuntimeData,
  handleChatRealtimeEvent,
  handlePersonaRealtimeEvent,
  handleRuntimeRealtimeEvent,
} from "./appRuntimeSyncHandlers";

describe("appRuntimeSyncHandlers", () => {
  it("applies initial runtime data into state setters", () => {
    const messagesRef = { current: [] as any[] };
    const setState = vi.fn();
    const setGoals = vi.fn();
    const setWorld = vi.fn();
    const setMessages = vi.fn();

    applyInitialRuntimeData(
      {
        state: {
          mode: "awake",
          focus_mode: "autonomy",
          current_thought: null,
          active_goal_ids: [],
          today_plan: null,
          last_action: null,
        },
        goals: [{ id: "goal-1", title: "整理今天的对话记忆", status: "active" }],
        world: null,
        messages: [{ id: "assistant-1", role: "assistant", content: "我在。" }],
      },
      messagesRef,
      { setGoals, setMessages, setState, setWorld },
    );

    expect(setState).toHaveBeenCalled();
    expect(setGoals).toHaveBeenCalledWith([{ id: "goal-1", title: "整理今天的对话记忆", status: "active" }]);
    expect(setWorld).toHaveBeenCalledWith(null);
    expect(setMessages).toHaveBeenCalledWith([{ id: "assistant-1", role: "assistant", content: "我在。" }]);
    expect(messagesRef.current).toEqual([{ id: "assistant-1", role: "assistant", content: "我在。" }]);
  });

  it("handles chat and runtime realtime updates through shared setters", () => {
    applyIncomingChatEvent.mockReturnValue({
      messages: [{ id: "assistant-1", role: "assistant", content: "我在。" }],
      error: "",
      clearPendingRequest: true,
      shouldSettleSending: true,
    });
    applyIncomingRuntimeEvent.mockReturnValue({
      state: {
        mode: "awake",
        focus_mode: "autonomy",
        current_thought: null,
        active_goal_ids: [],
        today_plan: null,
        last_action: null,
      },
      messages: [{ id: "assistant-2", role: "assistant", content: "继续中" }],
      goals: [{ id: "goal-2", title: "收住今天这条线", status: "active" }],
      world: null,
      macConsoleStatus: null,
      shouldSettleSending: true,
      error: "",
    });

    const messagesRef = { current: [] as any[] };
    const pendingRequestMessageRef = { current: { message: "继续说", requestKey: "request-1" } };
    const setMessages = vi.fn();
    const setIsSending = vi.fn();
    const setGoals = vi.fn();
    const setState = vi.fn();
    const setWorld = vi.fn();
    const setMacConsoleStatus = vi.fn();
    const setError = vi.fn();
    const updateFocusTransitionHint = vi.fn();

    expect(
      handleChatRealtimeEvent(
        { type: "chat_started", payload: { assistant_message_id: "assistant-1", response_id: "response-1" } },
        messagesRef,
        pendingRequestMessageRef,
        { setError, setIsSending, setMessages },
      ),
    ).toBe(true);
    expect(pendingRequestMessageRef.current).toBeNull();
    expect(setMessages).toHaveBeenCalledWith([{ id: "assistant-1", role: "assistant", content: "我在。" }]);

    expect(
      handleRuntimeRealtimeEvent(
        { type: "runtime_updated", payload: {} },
        messagesRef,
        {
          setError,
          setGoals,
          setIsSending,
          setMacConsoleStatus,
          setMessages,
          setState,
          setWorld,
        },
        updateFocusTransitionHint,
      ),
    ).toBe(true);
    expect(updateFocusTransitionHint).toHaveBeenCalled();
    expect(setState).toHaveBeenCalled();
    expect(setGoals).toHaveBeenCalledWith([{ id: "goal-2", title: "收住今天这条线", status: "active" }]);
    expect(setMacConsoleStatus).toHaveBeenCalledWith(null);
  });

  it("handles persona realtime updates when profile is available", () => {
    const setPersona = vi.fn();
    getPersonaProfileFromRealtimeEvent.mockReturnValue({
      name: "小晏",
      identity: "AI Agent Desktop",
      tone: "calm",
      features: { avatar_enabled: false },
    });

    expect(handlePersonaRealtimeEvent({ type: "persona_updated", payload: {} }, { setPersona })).toBe(true);
    expect(setPersona).toHaveBeenCalledWith({
      name: "小晏",
      identity: "AI Agent Desktop",
      tone: "calm",
      features: { avatar_enabled: false },
    });
  });
});
