import { describe, expect, test } from "vitest";

import type { ChatEntry } from "../ChatPanel";
import { applyIncomingChatEvent } from "./chatSync";

describe("chatSync", () => {
  test("settles sending and clears pending request when chat starts from a local request", () => {
    const result = applyIncomingChatEvent(
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
      clearPendingRequest: true,
      error: "",
      shouldSettleSending: false,
    });
    expect(result?.messages[0]).toMatchObject({
      id: "assistant-1",
      requestMessage: "继续说",
      state: "streaming",
    });
  });

  test("settles sending and surfaces error when assistant reply fails", () => {
    const current: ChatEntry[] = [
      {
        id: "assistant-1",
        role: "assistant",
        content: "前半句",
        state: "streaming",
        requestMessage: "继续说",
      },
    ];

    const result = applyIncomingChatEvent(
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
      clearPendingRequest: false,
      error: "network timeout",
      shouldSettleSending: true,
    });
    expect(result?.messages[0]).toMatchObject({
      id: "assistant-1",
      state: "failed",
      errorMessage: "network timeout",
    });
  });
});
