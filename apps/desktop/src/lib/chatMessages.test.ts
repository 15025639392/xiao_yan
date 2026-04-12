import { describe, expect, it } from "vitest";
import type { ChatEntry } from "../components/chat/chatTypes";
import { finalizeAssistantMessage, mergeMessages } from "./chatMessages";
import type { ChatHistoryMessage } from "./api";

describe("mergeMessages", () => {
  it("reconciles a locally finalized assistant bubble to avoid duplicate replies when runtime id changes", () => {
    const current: ChatEntry[] = [
      { id: "user-local-1", role: "user", content: "你好" },
      {
        id: "assistant_123",
        role: "assistant",
        content: "第一行\n\n第二行",
        requestMessage: "你好",
      },
    ];
    const incoming: ChatHistoryMessage[] = [
      { id: "mem-user-1", role: "user", content: "你好" },
      {
        id: "mem-assistant-1",
        role: "assistant",
        // Persisted text may normalize whitespace/newlines and differ from local render text.
        content: "第一行\n第二行",
        session_id: null,
      },
    ];

    const merged = mergeMessages(current, incoming);

    expect(merged).toHaveLength(2);
    const assistant = merged.find((entry) => entry.role === "assistant");
    expect(assistant?.id).toBe("mem-assistant-1");
    expect(assistant?.content).toBe("第一行\n第二行");
  });
});

describe("finalizeAssistantMessage", () => {
  it("stores knowledge references when assistant stream completes", () => {
    const current: ChatEntry[] = [
      {
        id: "assistant_1",
        role: "assistant",
        content: "我会继续按你的偏好来。",
        state: "streaming",
      },
    ];

    const finalized = finalizeAssistantMessage(
      current,
      "assistant_1",
      "我会继续按你的偏好来。",
      4,
      [
        {
          source: "wing_xiaoyan/knowledge",
          wing: "wing_xiaoyan",
          room: "knowledge",
          similarity: 0.88,
          excerpt: "你喜欢结构化输出。",
        },
      ],
    );

    expect(finalized[0].state).toBeUndefined();
    expect(finalized[0].knowledgeReferences).toEqual([
      {
        source: "wing_xiaoyan/knowledge",
        wing: "wing_xiaoyan",
        room: "knowledge",
        similarity: 0.88,
        excerpt: "你喜欢结构化输出。",
      },
    ]);
  });
});
