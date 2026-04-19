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
    const setMessages = vi.fn();

    applyInitialRuntimeData(
      {
        state: {
          mode: "awake",
          focus_mode: "autonomy",
          current_thought: null,
          last_action: null,
        },
        messages: [{ id: "assistant-1", role: "assistant", content: "我在。" }],
      },
      messagesRef,
      { setMessages, setState },
    );

    expect(setState).toHaveBeenCalled();
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
        last_action: null,
      },
      messages: [{ id: "assistant-2", role: "assistant", content: "继续中" }],
      shouldSettleSending: true,
      error: "",
    });

    const messagesRef = { current: [] as any[] };
    const pendingRequestMessageRef = { current: { message: "继续说", requestKey: "request-1" } };
    const setMessages = vi.fn();
    const setIsSending = vi.fn();
    const setState = vi.fn();
    const setError = vi.fn();
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
          setIsSending,
          setMessages,
          setState,
        },
      ),
    ).toBe(true);
    expect(setState).toHaveBeenCalled();
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
