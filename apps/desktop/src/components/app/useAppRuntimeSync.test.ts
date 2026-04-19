import { renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

const {
  loadInitialRuntimeData,
  applyIncomingRuntimeEvent,
  getPersonaProfileFromRealtimeEvent,
} = vi.hoisted(() => ({
  loadInitialRuntimeData: vi.fn(),
  applyIncomingRuntimeEvent: vi.fn(),
  getPersonaProfileFromRealtimeEvent: vi.fn(),
}));

const { applyIncomingChatEvent } = vi.hoisted(() => ({
  applyIncomingChatEvent: vi.fn(),
}));

const { subscribeAppRealtime } = vi.hoisted(() => ({
  subscribeAppRealtime: vi.fn(),
}));

vi.mock("./runtimeSync", () => ({
  loadInitialRuntimeData,
  applyIncomingRuntimeEvent,
  getPersonaProfileFromRealtimeEvent,
}));

vi.mock("./chatSync", () => ({
  applyIncomingChatEvent,
}));

vi.mock("../../lib/realtime", () => ({
  subscribeAppRealtime,
}));

import { useAppRuntimeSync } from "./useAppRuntimeSync";

describe("useAppRuntimeSync", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    loadInitialRuntimeData.mockReset();
    applyIncomingRuntimeEvent.mockReset();
    getPersonaProfileFromRealtimeEvent.mockReset();
    applyIncomingChatEvent.mockReset();
    subscribeAppRealtime.mockReset();
    window.location.hash = "";
  });

  it("hydrates initial runtime snapshot on mount", async () => {
    loadInitialRuntimeData.mockResolvedValue({
      state: {
        mode: "awake",
        focus_mode: "autonomy",
        current_thought: null,
        last_action: null,
      },
      messages: [{ id: "assistant-1", role: "assistant", content: "我在。" }],
    });
    subscribeAppRealtime.mockReturnValue(() => {});

    const messagesRef = { current: [] as any[] };
    const pendingRequestMessageRef = { current: null };
    const setState = vi.fn();
    const setMessages = vi.fn();

    renderHook(() =>
      useAppRuntimeSync({
        messagesRef,
        pendingRequestMessageRef,
        setError: vi.fn(),
        setIsSending: vi.fn(),
        setMessages,
        setPersona: vi.fn(),
        setState,
      }),
    );

    await waitFor(() => {
      expect(loadInitialRuntimeData).toHaveBeenCalled();
      expect(setState).toHaveBeenCalled();
    });

    expect(setMessages).toHaveBeenCalledWith([{ id: "assistant-1", role: "assistant", content: "我在。" }]);
    expect(messagesRef.current).toEqual([{ id: "assistant-1", role: "assistant", content: "我在。" }]);
  });

  it("routes runtime, chat, and persona realtime events to their respective handlers", async () => {
    loadInitialRuntimeData.mockResolvedValue({
      state: {
        mode: "sleeping",
        focus_mode: "sleeping",
        current_thought: null,
        last_action: null,
      },
      messages: null,
    });

    const listeners: Array<(event: any) => void> = [];
    subscribeAppRealtime.mockImplementation((listener) => {
      listeners.push(listener);
      return () => {};
    });

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
    getPersonaProfileFromRealtimeEvent.mockReturnValue({
      name: "小晏",
      identity: "AI Agent Desktop",
      tone: "calm",
      features: { avatar_enabled: false },
    });

    const messagesRef = { current: [] as any[] };
    const pendingRequestMessageRef = { current: { message: "继续说", requestKey: "request-1" } };
    const setMessages = vi.fn();
    const setIsSending = vi.fn();
    const setState = vi.fn();
    const setPersona = vi.fn();
    const setError = vi.fn();

    renderHook(() =>
      useAppRuntimeSync({
        messagesRef,
        pendingRequestMessageRef,
        setError,
        setIsSending,
        setMessages,
        setPersona,
        setState,
      }),
    );

    await waitFor(() => {
      expect(listeners).toHaveLength(2);
    });

    listeners[0]({
      type: "chat_started",
      payload: { assistant_message_id: "assistant-1", response_id: "response-1" },
    });
    expect(setMessages).toHaveBeenCalledWith([{ id: "assistant-1", role: "assistant", content: "我在。" }]);
    expect(setIsSending).toHaveBeenCalledWith(false);
    expect(pendingRequestMessageRef.current).toBeNull();

    listeners[0]({ type: "runtime_updated", payload: {} });
    expect(setState).toHaveBeenCalled();

    listeners[1]({ type: "persona_updated", payload: {} });
    expect(setPersona).toHaveBeenCalledWith({
      name: "小晏",
      identity: "AI Agent Desktop",
      tone: "calm",
      features: { avatar_enabled: false },
    });
    expect(setError).toHaveBeenCalled();
  });
});
