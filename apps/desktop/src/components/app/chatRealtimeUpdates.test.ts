import { describe, expect, test } from "vitest";

import type { ChatEntry } from "../ChatPanel";
import { applyChatRealtimeEvent } from "./chatRealtimeUpdates";

describe("applyChatRealtimeEvent", () => {
  test("hydrates assistant placeholder from pending request on chat_started", () => {
    const result = applyChatRealtimeEvent(
      [],
      {
        type: "chat_started",
        payload: {
          assistant_message_id: "assistant-1",
          response_id: "response-1",
          sequence: 1,
        },
      },
      { message: "继续说", requestKey: "request-1" },
    );

    expect(result).toMatchObject({
      error: "",
      clearPendingRequest: true,
    });
    expect(result?.messages).toEqual([
      {
        id: "assistant-1",
        role: "assistant",
        content: "",
        state: "streaming",
        requestKey: "request-1",
        requestMessage: "继续说",
        streamSequence: 1,
      },
    ]);
  });

  test("returns failed assistant update with surfaced error", () => {
    const current: ChatEntry[] = [
      {
        id: "assistant-1",
        role: "assistant",
        content: "前半句",
        state: "streaming",
        requestMessage: "继续说",
      },
    ];

    const result = applyChatRealtimeEvent(
      current,
      {
        type: "chat_failed",
        payload: {
          assistant_message_id: "assistant-1",
          error: "network timeout",
          sequence: 3,
        },
      },
      null,
    );

    expect(result).toMatchObject({
      error: "network timeout",
      clearPendingRequest: false,
    });
    expect(result?.messages[0]).toMatchObject({
      id: "assistant-1",
      state: "failed",
      errorMessage: "network timeout",
      requestMessage: "继续说",
    });
  });
});
