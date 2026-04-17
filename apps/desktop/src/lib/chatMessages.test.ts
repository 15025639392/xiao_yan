import { describe, expect, it } from "vitest";
import type { ChatEntry } from "../components/chat/chatTypes";
import { appendAssistantDelta, finalizeAssistantMessage, mergeMessages } from "./chatMessages";
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

  it("clears transient failed state when runtime history brings back the assistant reply", () => {
    const current: ChatEntry[] = [
      { id: "user-local-1", role: "user", content: "继续" },
      {
        id: "assistant_resume_local",
        role: "assistant",
        content: "前半句，",
        state: "failed",
        errorMessage: "request failed: 502",
        requestMessage: "继续",
      },
    ];
    const incoming: ChatHistoryMessage[] = [
      { id: "mem-user-2", role: "user", content: "继续" },
      {
        id: "mem-assistant-2",
        role: "assistant",
        content: "前半句，后半句。",
        session_id: null,
      },
    ];

    const merged = mergeMessages(current, incoming);
    const assistant = merged.find((entry) => entry.role === "assistant");

    expect(assistant?.content).toBe("前半句，后半句。");
    expect(assistant?.state).toBeUndefined();
    expect(assistant?.errorMessage).toBeUndefined();
  });

  it("clears transient failed state when runtime history brings back the user message", () => {
    const current: ChatEntry[] = [
      {
        id: "user-local-1",
        role: "user",
        content: "请帮我继续",
        state: "failed",
        errorMessage: "network timeout",
      },
    ];
    const incoming: ChatHistoryMessage[] = [
      {
        id: "mem-user-2",
        role: "user",
        content: "请帮我继续",
      },
    ];

    const merged = mergeMessages(current, incoming);

    expect(merged).toHaveLength(1);
    expect(merged[0]).toMatchObject({
      id: "mem-user-2",
      role: "user",
      content: "请帮我继续",
    });
    expect(merged[0].state).toBeUndefined();
    expect(merged[0].errorMessage).toBeUndefined();
  });

  it("prefers matching runtime user history to local pending user messages before generic fallback", () => {
    const current: ChatEntry[] = [
      {
        id: "user-1",
        role: "user",
        content: "收到",
      },
      {
        id: "mem-user-existing",
        role: "user",
        content: "收到",
      },
    ];
    const incoming: ChatHistoryMessage[] = [
      {
        id: "mem-user-new",
        role: "user",
        content: "收到",
      },
    ];

    const merged = mergeMessages(current, incoming);

    expect(merged).toHaveLength(2);
    expect(merged[0]).toMatchObject({
      id: "mem-user-new",
      role: "user",
      content: "收到",
    });
    expect(merged[1]).toMatchObject({
      id: "mem-user-existing",
      role: "user",
      content: "收到",
    });
  });

  it("matches repeated same-content assistant replies to the latest local request instead of duplicating", () => {
    const current: ChatEntry[] = [
      {
        id: "mem-user-old",
        role: "user",
        content: "你好",
        requestKey: "request-old",
      },
      {
        id: "mem-assistant-old",
        role: "assistant",
        content: "上一次回复",
        requestKey: "request-old",
        requestMessage: "你好",
      },
      {
        id: "user-local-new",
        role: "user",
        content: "你好",
        requestKey: "request-new",
      },
      {
        id: "assistant_local_new",
        role: "assistant",
        content: "",
        state: "streaming",
        requestKey: "request-new",
        requestMessage: "你好",
      },
    ];
    const incoming: ChatHistoryMessage[] = [
      { id: "mem-user-old", role: "user", content: "你好" },
      { id: "mem-assistant-old", role: "assistant", content: "上一次回复", session_id: null },
      { id: "mem-user-new", role: "user", content: "你好" },
      { id: "mem-assistant-new", role: "assistant", content: "这一次回复", session_id: null },
    ];

    const merged = mergeMessages(current, incoming);

    expect(merged).toHaveLength(4);
    expect(merged[2]).toMatchObject({
      id: "mem-user-new",
      role: "user",
      content: "你好",
      requestKey: "request-new",
    });
    expect(merged[3]).toMatchObject({
      role: "assistant",
      content: "这一次回复",
      requestKey: "request-new",
      requestMessage: "你好",
    });
    expect(merged.filter((entry) => entry.role === "assistant" && entry.content === "这一次回复")).toHaveLength(1);
  });
});

describe("finalizeAssistantMessage", () => {
  it("preserves request and reasoning linkage when the first assistant delta creates the bubble", () => {
    const appended = appendAssistantDelta(
      [],
      "assistant_0",
      "你好",
      1,
      "reasoning_0",
      {
        session_id: "reasoning_0",
        phase: "exploring",
        step_index: 1,
        summary: "先起一稿。",
        updated_at: "2026-04-16T10:00:00+00:00",
      },
      "request_0",
    );

    expect(appended).toEqual([
      {
        id: "assistant_0",
        role: "assistant",
        content: "你好",
        state: "streaming",
        requestKey: "request_0",
        reasoningSessionId: "reasoning_0",
        reasoningState: {
          session_id: "reasoning_0",
          phase: "exploring",
          step_index: 1,
          summary: "先起一稿。",
          updated_at: "2026-04-16T10:00:00+00:00",
        },
        streamSequence: 1,
      },
    ]);
  });

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
