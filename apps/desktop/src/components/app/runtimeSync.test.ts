import { describe, expect, it, vi } from "vitest";

const {
  fetchGoals,
  fetchMessages,
  fetchState,
  fetchWorld,
} = vi.hoisted(() => ({
  fetchGoals: vi.fn(),
  fetchMessages: vi.fn(),
  fetchState: vi.fn(),
  fetchWorld: vi.fn(),
}));

vi.mock("../../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../../lib/api")>("../../lib/api");
  return {
    ...actual,
    fetchGoals,
    fetchMessages,
    fetchState,
    fetchWorld,
  };
});

import type { ChatEntry } from "../ChatPanel";
import {
  applyIncomingRuntimeEvent,
  getPersonaProfileFromRealtimeEvent,
  loadInitialRuntimeData,
} from "./runtimeSync";

describe("runtimeSync", () => {
  it("loads initial chat runtime data with lazy message hydration", async () => {
    fetchState.mockResolvedValue({
      mode: "awake",
      focus_mode: "autonomy",
      current_thought: null,
      active_goal_ids: [],
      today_plan: null,
      last_action: null,
    });
    fetchGoals.mockResolvedValue({ goals: [{ id: "goal-1", title: "整理对话记忆", status: "active" }] });
    fetchWorld.mockResolvedValue(null);
    fetchMessages.mockResolvedValue({
      messages: [
        { id: "user-1", role: "user", content: "你好" },
        { id: "assistant-1", role: "assistant", content: "我在。" },
      ],
    });

    const result = await loadInitialRuntimeData("chat");

    expect(fetchMessages).toHaveBeenCalled();
    expect(result.goals).toHaveLength(1);
    expect(result.messages).toHaveLength(2);
    expect(result.messages?.[0]).toMatchObject({ id: "user-1", role: "user", content: "你好" });
    expect(result.messages?.[1]).toMatchObject({
      id: "assistant-1",
      role: "assistant",
      content: "我在。",
      requestMessage: "你好",
    });
  });

  it("applies incoming runtime event and exposes settled sending hint", () => {
    const currentMessages: ChatEntry[] = [{ id: "user-local-1", role: "user", content: "你好" }];

    const result = applyIncomingRuntimeEvent(currentMessages, {
      type: "runtime_updated",
      payload: {
        state: {
          mode: "awake",
          focus_mode: "autonomy",
          current_thought: null,
          active_goal_ids: [],
          today_plan: null,
          last_action: null,
        },
        messages: [
          { id: "user-1", role: "user", content: "你好" },
          { id: "assistant-1", role: "assistant", content: "我在。", session_id: null },
        ],
        goals: [],
        world: null,
        autobio: [],
        mac_console_status: null,
      },
    });

    expect(result?.messages).toHaveLength(2);
    expect(result?.shouldSettleSending).toBe(true);
    expect(result?.error).toBe("");
  });

  it("extracts persona profile from snapshot and persona_updated events", () => {
    const profile = {
      name: "小晏",
      identity: "AI Agent Desktop",
      tone: "calm",
      features: { avatar_enabled: false },
    };

    expect(
      getPersonaProfileFromRealtimeEvent({
        type: "persona_updated",
        payload: {
          profile,
          emotion: {
            primary_emotion: "calm",
            primary_intensity: "none",
            secondary_emotion: null,
            secondary_intensity: "none",
            mood_valence: 0,
            arousal: 0,
            is_calm: true,
            active_entry_count: 0,
            active_entries: [],
            last_updated: null,
          },
        },
      }),
    ).toEqual(profile);
  });
});
