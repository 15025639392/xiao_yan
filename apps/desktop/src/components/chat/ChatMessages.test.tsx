import { fireEvent, render, screen, within } from "@testing-library/react";
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

beforeEach(() => {
  markdownRenderSpy.mockClear();
});

test("shows response reference only on the latest assistant message", () => {
  const { container } = render(
    <ChatMessages
      assistantName="小晏"
      messages={[
        { id: "user-1", role: "user", content: "你好" },
        { id: "assistant-1", role: "assistant", content: "我在听。" },
        { id: "assistant-2", role: "assistant", content: "我更想先把真实判断告诉你。" },
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

  expect(screen.getAllByText("本次回应参考")).toHaveLength(1);

  const assistantMessages = container.querySelectorAll(".chat-message--assistant");
  expect(assistantMessages).toHaveLength(2);
  expect(within(assistantMessages[0] as HTMLElement).queryByText("本次回应参考")).toBeNull();
  expect(within(assistantMessages[1] as HTMLElement).getByText("本次回应参考")).toBeInTheDocument();
});

test("shows retry action for failed user message", () => {
  const onRetry = vi.fn();

  render(
    <ChatMessages
      assistantName="小晏"
      messages={[
        { id: "user-failed", role: "user", content: "这条消息发送失败了", state: "failed" },
      ]}
      relationship={null}
      isSending={false}
      showMemoryContext={new Set()}
      onToggleMemoryContext={() => {}}
      onRetry={onRetry}
      onDraftChange={() => {}}
    />,
  );

  fireEvent.click(screen.getByRole("button", { name: "重发" }));
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

  expect(screen.getByText("知识来源")).toBeInTheDocument();
  expect(screen.getByText("wing_xiaoyan/knowledge")).toBeInTheDocument();
  expect(screen.getByText("相似度 0.88")).toBeInTheDocument();
  expect(screen.getByText("你喜欢结构化输出。")).toBeInTheDocument();
});
