import { describe, expect, it } from "vitest";

import type { ChatEntry } from "../ChatPanel";
import type { ChatHistoryMessage } from "../../lib/api";
import { syncMessagesFromRuntime } from "./chatRuntimeMessages";

describe("syncMessagesFromRuntime", () => {
  it("keeps unsynced local conversation when runtime snapshot is empty", () => {
    const current: ChatEntry[] = [
      {
        id: "user-1",
        role: "user",
        content: "你好",
      },
      {
        id: "assistant-local-1",
        role: "assistant",
        content: "我在。",
        requestMessage: "你好",
      },
      {
        id: "assistant-streaming-1",
        role: "assistant",
        content: "我再补一句",
        state: "streaming",
        requestMessage: "你好",
      },
    ];

    expect(syncMessagesFromRuntime(current, [])).toEqual(current);
  });

  it("uses merged runtime history when snapshot is available", () => {
    const current: ChatEntry[] = [
      { id: "user-1", role: "user", content: "你好" },
      { id: "assistant_1", role: "assistant", content: "旧内容", requestMessage: "你好" },
    ];
    const incoming: ChatHistoryMessage[] = [
      { id: "mem-user-1", role: "user", content: "你好" },
      { id: "mem-assistant-1", role: "assistant", content: "新内容", session_id: null },
    ];

    const merged = syncMessagesFromRuntime(current, incoming);

    expect(merged).toHaveLength(2);
    expect(merged[1]).toMatchObject({
      id: "mem-assistant-1",
      content: "新内容",
    });
  });
});
