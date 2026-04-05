import { fireEvent, render, screen } from "@testing-library/react";
import { vi } from "vitest";

import { ChatPanel } from "./ChatPanel";

test("renders the console header and speaker labels in Chinese", () => {
  render(
    <ChatPanel
      draft="你好"
      isSending={false}
      messages={[
        { id: "1", role: "user", content: "你好" },
        { id: "2", role: "assistant", content: "我在。" },
      ]}
      onDraftChange={vi.fn()}
      onSend={vi.fn()}
    />,
  );

  expect(screen.getByText("对话控制台")).toBeInTheDocument();
  expect(screen.getByText("你")).toBeInTheDocument();
  expect(screen.getByText("小晏")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "发送" })).toBeInTheDocument();
});

test("disables send while sending or when the draft is empty", () => {
  const onSend = vi.fn();

  const { rerender } = render(
    <ChatPanel
      draft=""
      isSending={false}
      messages={[]}
      onDraftChange={vi.fn()}
      onSend={onSend}
    />,
  );

  expect(screen.getByRole("button", { name: "发送" })).toBeDisabled();

  rerender(
    <ChatPanel
      draft="你好"
      isSending={true}
      messages={[]}
      onDraftChange={vi.fn()}
      onSend={onSend}
    />,
  );

  expect(screen.getByRole("button", { name: "发送中" })).toBeDisabled();
});

test("forwards input changes and send events", () => {
  const onDraftChange = vi.fn();
  const onSend = vi.fn();

  render(
    <ChatPanel
      draft="你好吗"
      isSending={false}
      messages={[]}
      onDraftChange={onDraftChange}
      onSend={onSend}
    />,
  );

  fireEvent.change(screen.getByLabelText("对话输入"), {
    target: { value: "晚点再聊" },
  });
  fireEvent.click(screen.getByRole("button", { name: "发送" }));

  expect(onDraftChange).toHaveBeenCalledWith("晚点再聊");
  expect(onSend).toHaveBeenCalledTimes(1);
});
