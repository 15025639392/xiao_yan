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

  it("hydrates assistant reasoning fields from runtime history", () => {
    const current: ChatEntry[] = [
      { id: "user-local-1", role: "user", content: "继续" },
      {
        id: "assistant_abc",
        role: "assistant",
        content: "先分析一下",
        requestMessage: "继续",
      },
    ];
    const incoming: ChatHistoryMessage[] = [
      { id: "mem-user-2", role: "user", content: "继续" },
      {
        id: "mem-assistant-2",
        role: "assistant",
        content: "这是结论",
        session_id: null,
        reasoning_session_id: "reasoning_abc",
        reasoning_state: {
          session_id: "reasoning_abc",
          phase: "exploring",
          step_index: 3,
          summary: "继续收敛",
          updated_at: "2026-04-16T10:00:00+00:00",
        },
      },
    ];

    const merged = mergeMessages(current, incoming);
    const assistant = merged.find((entry) => entry.role === "assistant");

    expect(assistant?.id).toBe("mem-assistant-2");
    expect(assistant?.reasoningSessionId).toBe("reasoning_abc");
    expect(assistant?.reasoningState?.step_index).toBe(3);
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

  it("stores reasoning state when assistant stream completes", () => {
    const current: ChatEntry[] = [
      {
        id: "assistant_2",
        role: "assistant",
        content: "我先分析一下。",
        state: "streaming",
      },
    ];

    const finalized = finalizeAssistantMessage(
      current,
      "assistant_2",
      "这是结论。",
      5,
      undefined,
      "reasoning_123",
      {
        session_id: "reasoning_123",
        phase: "exploring",
        step_index: 2,
        summary: "先收敛问题，再给出结论。",
        updated_at: "2026-04-16T10:00:00+00:00",
      },
    );

    expect(finalized[0].reasoningSessionId).toBe("reasoning_123");
    expect(finalized[0].reasoningState).toEqual({
      session_id: "reasoning_123",
      phase: "exploring",
      step_index: 2,
      summary: "先收敛问题，再给出结论。",
      updated_at: "2026-04-16T10:00:00+00:00",
    });
  });
});
