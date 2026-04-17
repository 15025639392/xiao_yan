import { render, screen } from "@testing-library/react";
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

test("keeps assistant body as the primary focus and moves status into details", () => {
  const { container } = render(
    <ChatMessages
      assistantName="小晏"
      messages={[
        {
          id: "assistant-failed",
          role: "assistant",
          content: "先给你结论，再展开原因。",
          state: "failed",
          errorMessage: "连接暂时断开了",
          requestMessage: "继续说",
        },
      ]}
      relationship={null}
      isSending={false}
      showMemoryContext={new Set()}
      onToggleMemoryContext={() => {}}
      onDraftChange={() => {}}
    />,
  );

  const body = container.querySelector(".chat-message__body--markdown");
  const details = container.querySelector(".chat-message__details");

  expect(body).not.toBeNull();
  expect(details).not.toBeNull();
  expect(body?.compareDocumentPosition(details as Node) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  expect(screen.getByText("小晏刚才停下来了：连接暂时断开了")).toBeInTheDocument();
});

test("keeps failed user status inside the details area", () => {
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
      onDraftChange={() => {}}
    />,
  );

  expect(screen.getByText("这句话还没顺利送到小晏那里：网络有点不稳").closest(".chat-message__details")).not.toBeNull();
});

test("keeps memory context affordance available for assistant messages", () => {
  render(
    <ChatMessages
      assistantName="小晏"
      messages={[
        {
          id: "assistant-memory",
          role: "assistant",
          content: "我记得你希望先看结论。",
          relatedMemories: [
            {
              id: "memory-1",
              kind: "semantic",
              content: "用户偏好先给结论再展开。",
              strength: "normal",
              starred: true,
              created_at: "2026-04-17T00:00:00Z",
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

  expect(screen.getByRole("button", { name: /相关记忆 \(1\)/ })).toBeInTheDocument();
});
