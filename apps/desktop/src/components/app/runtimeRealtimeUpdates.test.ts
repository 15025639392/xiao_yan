import { describe, expect, test } from "vitest";

import type { ChatEntry } from "../ChatPanel";
import { applyRuntimeRealtimeEvent, getRuntimeRealtimePayload } from "./runtimeRealtimeUpdates";

describe("runtimeRealtimeUpdates", () => {
  test("extracts runtime payload from snapshot and runtime_updated events", () => {
    const runtimePayload = {
      state: {
        mode: "awake" as const,
        focus_mode: "chat" as const,
        current_thought: null,
        active_goal_ids: [],
        today_plan: null,
        last_action: null,
      },
      messages: [],
      goals: [],
      world: null,
      autobio: [],
      mac_console_status: null,
    };

    expect(
      getRuntimeRealtimePayload({
        type: "snapshot",
        payload: {
          runtime: runtimePayload,
          memory: {
            summary: {
              total_estimated: 0,
              by_kind: {},
              recent_count: 0,
              strong_memories: 0,
              relationship: {
                available: false,
                boundaries: [],
                commitments: [],
                preferences: [],
              },
              available: false,
            },
            relationship: {
              available: false,
              boundaries: [],
              commitments: [],
              preferences: [],
            },
            timeline: [],
          },
          persona: {
            profile: {
              name: "小晏",
              identity: "AI Agent Desktop",
              tone: "calm",
              features: {
                avatar_enabled: false,
              },
            },
            emotion: {
              primary_emotion: "calm",
              primary_intensity: "mild",
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
        },
      }),
    ).toEqual(runtimePayload);

    expect(
      getRuntimeRealtimePayload({
        type: "runtime_updated",
        payload: runtimePayload,
      }),
    ).toEqual(runtimePayload);
  });

  test("applies runtime message sync while keeping runtime fields together", () => {
    const currentMessages: ChatEntry[] = [
      { id: "user-local-1", role: "user", content: "你好" },
      { id: "assistant-local-1", role: "assistant", content: "我在。", requestMessage: "你好" },
    ];

    const result = applyRuntimeRealtimeEvent(currentMessages, {
      type: "runtime_updated",
      payload: {
        state: {
          mode: "awake",
          focus_mode: "chat",
          current_thought: null,
          active_goal_ids: [],
          today_plan: null,
          last_action: null,
        },
        messages: [
          { id: "mem-user-1", role: "user", content: "你好" },
          { id: "mem-assistant-1", role: "assistant", content: "我在。", session_id: null },
        ],
        goals: [],
        world: null,
        autobio: [],
      },
    });

    expect(result?.messages).toHaveLength(2);
    expect(result?.messages[1]).toMatchObject({
      id: "mem-assistant-1",
      content: "我在。",
    });
    expect(result?.error).toBe("");
  });
});
