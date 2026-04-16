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
            relationship: {
              available: false,
              boundaries: [],
              commitments: [],
              preferences: [],
            },
            available: true,
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
            identity: "数字人",
            origin_story: "",
            features: {
              avatar_enabled: true,
            },
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
              is_calm: true,
              active_entry_count: 0,
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

  test("reorders chat events by session sequence before notifying listeners", () => {
    vi.stubGlobal("WebSocket", MockWebSocket as unknown as typeof WebSocket);

    const listener = vi.fn();
    const unsubscribe = subscribeAppRealtime(listener);
    const socket = MockWebSocket.instances[0];

    socket.open();
    socket.emit({
      type: "chat_started",
      payload: {
        assistant_message_id: "assistant_1",
        response_id: "resp_1",
        session_id: "assistant_1",
        sequence: 1,
      },
    });
    socket.emit({
      type: "chat_delta",
      payload: {
        assistant_message_id: "assistant_1",
        delta: "你",
        session_id: "assistant_1",
        sequence: 2,
      },
    });
    socket.emit({
      type: "chat_completed",
      payload: {
        assistant_message_id: "assistant_1",
        response_id: "resp_1",
        content: "你好",
        knowledge_references: [
          {
            source: "wing_xiaoyan/knowledge",
            wing: "wing_xiaoyan",
            room: "knowledge",
            similarity: 0.88,
            excerpt: "你喜欢结构化输出。",
          },
        ],
        session_id: "assistant_1",
        sequence: 4,
      },
    });
    socket.emit({
      type: "chat_delta",
      payload: {
        assistant_message_id: "assistant_1",
        delta: "好",
        session_id: "assistant_1",
        sequence: 3,
      },
    });

    expect(listener.mock.calls).toEqual([
      [
        {
          type: "chat_started",
          payload: {
            assistant_message_id: "assistant_1",
            response_id: "resp_1",
            session_id: "assistant_1",
            sequence: 1,
          },
        },
      ],
      [
        {
          type: "chat_delta",
          payload: {
            assistant_message_id: "assistant_1",
            delta: "你",
            session_id: "assistant_1",
            sequence: 2,
          },
        },
      ],
      [
        {
          type: "chat_delta",
          payload: {
            assistant_message_id: "assistant_1",
            delta: "好",
            session_id: "assistant_1",
            sequence: 3,
          },
        },
      ],
      [
        {
          type: "chat_completed",
          payload: {
            assistant_message_id: "assistant_1",
            response_id: "resp_1",
            content: "你好",
            knowledge_references: [
              {
                source: "wing_xiaoyan/knowledge",
                wing: "wing_xiaoyan",
                room: "knowledge",
                similarity: 0.88,
                excerpt: "你喜欢结构化输出。",
              },
            ],
            session_id: "assistant_1",
            sequence: 4,
          },
        },
      ],
    ]);

    unsubscribe();
  });
});
