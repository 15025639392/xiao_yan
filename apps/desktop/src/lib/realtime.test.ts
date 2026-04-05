import { afterEach, describe, expect, test, vi } from "vitest";

import {
  resetAppRealtimeForTests,
  subscribeAppRealtime,
  type AppRealtimeEvent,
} from "./realtime";

class MockWebSocket {
  static instances: MockWebSocket[] = [];

  onopen: ((event: Event) => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;
  onclose: ((event: CloseEvent) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;
  readyState = 0;
  url: string;

  constructor(url: string) {
    this.url = url;
    MockWebSocket.instances.push(this);
  }

  open() {
    this.readyState = 1;
    this.onopen?.(new Event("open"));
  }

  emit(message: AppRealtimeEvent) {
    this.onmessage?.(
      new MessageEvent("message", {
        data: JSON.stringify(message),
      }),
    );
  }

  close() {
    this.readyState = 3;
    this.onclose?.(new CloseEvent("close"));
  }
}

describe("app realtime client", () => {
  afterEach(() => {
    resetAppRealtimeForTests();
    vi.restoreAllMocks();
    MockWebSocket.instances = [];
  });

  test("shares one websocket and replays latest snapshot to late subscribers", () => {
    vi.stubGlobal("WebSocket", MockWebSocket as unknown as typeof WebSocket);

    const firstListener = vi.fn();
    const secondListener = vi.fn();

    const unsubscribeFirst = subscribeAppRealtime(firstListener);
    const socket = MockWebSocket.instances[0];
    expect(socket.url).toBe("ws://127.0.0.1:8000/ws/app");

    socket.open();
    socket.emit({
      type: "snapshot",
      payload: {
        runtime: {
          state: {
            mode: "awake",
            focus_mode: "autonomy",
            current_thought: null,
            active_goal_ids: [],
            today_plan: null,
            last_action: null,
            self_programming_job: null,
          },
          messages: [],
          goals: [],
          world: null,
          autobio: [],
        },
        memory: {
          summary: {
            total_estimated: 0,
            by_kind: {},
            recent_count: 0,
            strong_memories: 0,
            available: true,
          },
          timeline: [],
        },
        persona: {
          profile: {
            name: "小晏",
            identity: "数字人",
            origin_story: "",
            created_at: null,
            personality: {
              openness: 72,
              conscientiousness: 60,
              extraversion: 40,
              agreeableness: 68,
              neuroticism: 45,
            },
            speaking_style: {
              formal_level: "casual",
              sentence_style: "mixed",
              expression_habit: "gentle",
              emoji_usage: "sometimes",
              verbal_tics: [],
              response_length: "medium",
            },
            values: {
              core_values: [],
              boundaries: [],
            },
            emotion: {
              primary_emotion: "calm",
              primary_intensity: "none",
              secondary_emotion: null,
              secondary_intensity: "none",
              mood_valence: 0,
              arousal: 0,
              active_entries: [],
              last_updated: null,
            },
            version: 1,
          },
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
      },
    });

    const unsubscribeSecond = subscribeAppRealtime(secondListener);

    expect(firstListener).toHaveBeenCalledTimes(1);
    expect(secondListener).toHaveBeenCalledTimes(1);
    expect(MockWebSocket.instances).toHaveLength(1);

    unsubscribeFirst();
    unsubscribeSecond();
  });
});
