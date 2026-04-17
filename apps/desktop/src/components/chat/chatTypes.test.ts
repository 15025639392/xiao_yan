import { describe, expect, test } from "vitest";

import {
  hasKnowledgeReferences,
  hasRecoverableAssistantReply,
  hasRelatedMemories,
  hasRetryableUserSend,
  isAssistantChatEntry,
  isUserChatEntry,
  type ChatEntry,
} from "./chatTypes";

describe("chatTypes helpers", () => {
  test("classifies assistant and user entries", () => {
    const assistant: ChatEntry = { id: "assistant-1", role: "assistant", content: "我在。" };
    const user: ChatEntry = { id: "user-1", role: "user", content: "你好" };

    expect(isAssistantChatEntry(assistant)).toBe(true);
    expect(isUserChatEntry(assistant)).toBe(false);
    expect(isAssistantChatEntry(user)).toBe(false);
    expect(isUserChatEntry(user)).toBe(true);
  });

  test("detects recoverable assistant replies and retryable user sends", () => {
    const failedAssistant: ChatEntry = {
      id: "assistant-failed",
      role: "assistant",
      content: "我先说到这",
      state: "failed",
      requestMessage: "继续说",
    };
    const failedUser: ChatEntry = {
      id: "user-failed",
      role: "user",
      content: "帮我整理一下",
      state: "failed",
    };

    expect(hasRecoverableAssistantReply(failedAssistant)).toBe(true);
    expect(hasRecoverableAssistantReply(failedUser)).toBe(false);
    expect(hasRetryableUserSend(failedUser)).toBe(true);
    expect(hasRetryableUserSend(failedAssistant)).toBe(false);
  });

  test("detects optional message enrichments separately from message core", () => {
    const enrichedAssistant: ChatEntry = {
      id: "assistant-1",
      role: "assistant",
      content: "我按你熟悉的方式说。",
      knowledgeReferences: [
        {
          source: "wing_xiaoyan/knowledge",
          wing: "wing_xiaoyan",
          room: "knowledge",
          similarity: 0.9,
          excerpt: "用户喜欢结构化回答。",
        },
      ],
      relatedMemories: [
        {
          id: "memory-1",
          kind: "conversation",
          content: "用户希望先给结论。",
          strength: "medium",
          starred: false,
          created_at: "2026-04-17T00:00:00Z",
        },
      ],
    };

    expect(hasKnowledgeReferences(enrichedAssistant)).toBe(true);
    expect(hasRelatedMemories(enrichedAssistant)).toBe(true);
    expect(
      hasKnowledgeReferences({ id: "assistant-2", role: "assistant", content: "我继续说。" }),
    ).toBe(false);
  });
});
