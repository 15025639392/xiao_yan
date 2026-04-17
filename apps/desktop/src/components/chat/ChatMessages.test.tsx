import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, vi } from "vitest";

const { markdownRenderSpy } = vi.hoisted(() => ({
  markdownRenderSpy: vi.fn(),
}));

vi.mock("../MarkdownMessage", () => ({
  MarkdownMessage: ({ content }: { content: string }) => {
    markdownRenderSpy(content);
    return <div data-testid="markdown-message">{content}</div>;
  },
}));

import { ChatMessages } from "./ChatMessages";
import { getChatMessageDisplayState } from "./chatMessagePresentation";

beforeEach(() => {
  markdownRenderSpy.mockClear();
});

test("does not render relationship reference inside assistant messages", () => {
  render(
    <ChatMessages
      assistantName="小晏"
      messages={[
        { id: "user-1", role: "user", content: "你好" },
        { id: "assistant-1", role: "assistant", content: "我在听。" },
      ]}
      relationship={{
        available: true,
        boundaries: ["先直接给真实判断"],
        commitments: ["答应你先提示风险"],
        preferences: ["喜欢一起推演"],
      }}
      isSending={false}
      showMemoryContext={new Set()}
      onToggleMemoryContext={() => {}}
      onDraftChange={() => {}}
    />,
  );

  expect(screen.queryByText("本次回应参考")).toBeNull();
});

test("shows retry action for failed user message", () => {
  const onRetry = vi.fn();

  render(
    <ChatMessages
      assistantName="小晏"
      messages={[
        {
          id: "user-failed",
          role: "user",
          content: "这条消息发送失败了",
          state: "failed",
          errorMessage: "网络有点不稳",
        },
      ]}
      relationship={null}
      isSending={false}
      showMemoryContext={new Set()}
      onToggleMemoryContext={() => {}}
      onRetry={onRetry}
      onDraftChange={() => {}}
    />,
  );

  expect(screen.getByText("这句话还没顺利送到小晏那里：网络有点不稳")).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "重新发送" }));
  expect(onRetry).toHaveBeenCalledTimes(1);
  expect(onRetry.mock.calls[0][0]).toMatchObject({ id: "user-failed", role: "user" });
});

test("does not rerender markdown when messages props are unchanged", () => {
  const messages = [{ id: "assistant-1", role: "assistant", content: "这是一次回答" }];
  const showMemoryContext = new Set<string>();
  const onToggleMemoryContext = vi.fn();
  const onDraftChange = vi.fn();

  const { rerender } = render(
    <ChatMessages
      assistantName="小晏"
      messages={messages}
      relationship={null}
      isSending={false}
      showMemoryContext={showMemoryContext}
      onToggleMemoryContext={onToggleMemoryContext}
      onDraftChange={onDraftChange}
    />,
  );

  expect(markdownRenderSpy).toHaveBeenCalledTimes(1);

  rerender(
    <ChatMessages
      assistantName="小晏"
      messages={messages}
      relationship={null}
      isSending={false}
      showMemoryContext={showMemoryContext}
      onToggleMemoryContext={onToggleMemoryContext}
      onDraftChange={onDraftChange}
    />,
  );

  expect(markdownRenderSpy).toHaveBeenCalledTimes(1);
});

test("renders knowledge references for assistant messages", () => {
  render(
    <ChatMessages
      assistantName="小晏"
      messages={[
        { id: "user-1", role: "user", content: "你还记得我偏好吗" },
        {
          id: "assistant-1",
          role: "assistant",
          content: "我会继续按你的偏好来。",
          knowledgeReferences: [
            {
              source: "wing_xiaoyan/knowledge",
              wing: "wing_xiaoyan",
              room: "knowledge",
              similarity: 0.883,
              excerpt: "你喜欢结构化输出。",
            },
          ],
        },
      ]}
      relationship={null}
      isSending={false}
      showMemoryContext={new Set()}
      onToggleMemoryContext={() => {}}
      onDraftChange={() => {}}
    />,
  );

  expect(screen.getByRole("button", { name: "回复来源 (1)" })).toBeInTheDocument();
  expect(screen.queryByText("知识来源")).toBeNull();

  fireEvent.click(screen.getByRole("button", { name: "回复来源 (1)" }));
  expect(screen.getByText("知识来源")).toBeInTheDocument();
  expect(screen.getByText("wing_xiaoyan/knowledge")).toBeInTheDocument();
  expect(screen.getByText("相似度 0.88")).toBeInTheDocument();
  expect(screen.getByText("你喜欢结构化输出。")).toBeInTheDocument();
});

test("keeps streaming reasoning copy out of the way once assistant text is visible", () => {
  render(
    <ChatMessages
      assistantName="小晏"
      messages={[
        {
          id: "assistant-1",
          role: "assistant",
          content: "我先继续推理。",
          state: "streaming",
          reasoningSessionId: "reasoning_1",
          reasoningState: {
            session_id: "reasoning_1",
            phase: "exploring",
            step_index: 3,
            summary: "先收敛约束，再确认可行路径。",
            updated_at: "2026-04-16T10:00:00+00:00",
          },
        },
      ]}
      relationship={null}
      isSending={false}
      showMemoryContext={new Set()}
      onToggleMemoryContext={() => {}}
      onDraftChange={() => {}}
    />,
  );

  expect(screen.queryByText("先收敛约束，再确认可行路径。")).toBeNull();
  expect(screen.getByText("我先继续推理。▍")).toBeInTheDocument();
  expect(screen.queryByText("持续推理")).toBeNull();
  expect(screen.queryByText("步骤 3")).toBeNull();
  expect(screen.queryByText("阶段 exploring")).toBeNull();
});

test("renders natural streaming status while waiting for assistant text", () => {
  render(
    <ChatMessages
      assistantName="小晏"
      messages={[
        {
          id: "assistant-1",
          role: "assistant",
          content: "",
          state: "streaming",
          reasoningSessionId: "reasoning_1",
          reasoningState: {
            session_id: "reasoning_1",
            phase: "exploring",
            step_index: 3,
            summary: "先收敛约束，再确认可行路径。",
            updated_at: "2026-04-16T10:00:00+00:00",
          },
        },
      ]}
      relationship={null}
      isSending={false}
      showMemoryContext={new Set()}
      onToggleMemoryContext={() => {}}
      onDraftChange={() => {}}
    />,
  );

  expect(screen.getByText("先收敛约束，再确认可行路径。")).toBeInTheDocument();
  expect(screen.queryByText("持续推理")).toBeNull();
  expect(screen.queryByText("步骤 3")).toBeNull();
  expect(screen.queryByText("阶段 exploring")).toBeNull();
});

test("renders placeholder copy while waiting for assistant content", () => {
  render(
    <ChatMessages
      assistantName="小晏"
      messages={[{ id: "user-1", role: "user", content: "你在吗" }]}
      relationship={null}
      isSending={true}
      showMemoryContext={new Set()}
      onToggleMemoryContext={() => {}}
      onDraftChange={() => {}}
    />,
  );

  expect(screen.getByText("小晏正在整理这句话。")).toBeInTheDocument();
});

test("shows resume copy for failed assistant message", () => {
  const onResume = vi.fn();

  render(
    <ChatMessages
      assistantName="小晏"
      messages={[
        {
          id: "assistant-failed",
          role: "assistant",
          content: "我先把结论说一半",
          state: "failed",
          errorMessage: "连接暂时断开了",
          requestMessage: "继续说",
        },
      ]}
      relationship={null}
      isSending={false}
      showMemoryContext={new Set()}
      onToggleMemoryContext={() => {}}
      onResume={onResume}
      onDraftChange={() => {}}
    />,
  );

  expect(screen.getByText("小晏刚才停下来了：连接暂时断开了")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "接着说完" }));
  expect(onResume).toHaveBeenCalledTimes(1);
});

test("derives assistant display state from message fields in one place", () => {
  expect(
    getChatMessageDisplayState(
      {
        id: "assistant-streaming",
        role: "assistant",
        content: "",
        state: "streaming",
        reasoningState: {
          session_id: "reasoning_1",
          phase: "exploring",
          step_index: 1,
          summary: "我先把线索理顺。",
          updated_at: "2026-04-18T00:00:00Z",
        },
        knowledgeReferences: [
          {
            source: "wing_xiaoyan/knowledge",
            wing: "wing_xiaoyan",
            room: "knowledge",
            similarity: 0.9,
            excerpt: "记住用户喜欢结构化回答。",
          },
        ],
        relatedMemories: [
          {
            id: "memory-1",
            kind: "conversation",
            content: "用户偏好先给结论。",
            strength: "medium",
            starred: false,
            created_at: "2026-04-17T00:00:00Z",
          },
        ],
      },
      "小晏",
    ),
  ).toMatchObject({
    bodyMode: "streaming-placeholder",
    status: { text: "我先把线索理顺。", tone: "muted" },
    showKnowledgeContext: true,
    showMemoryContext: true,
    showResumeAction: false,
    showRetryAction: false,
  });
});

test("derives failed user display state without assistant-only affordances", () => {
  expect(
    getChatMessageDisplayState(
      {
        id: "user-failed",
        role: "user",
        content: "帮我记一下",
        state: "failed",
        errorMessage: "network timeout",
      },
      "小晏",
    ),
  ).toMatchObject({
    bodyMode: "plain-text",
    status: { text: "这句话还没顺利送到小晏那里：network timeout", tone: "failed" },
    showKnowledgeContext: false,
    showMemoryContext: false,
    showResumeAction: false,
    showRetryAction: true,
  });
});
