import { fireEvent, render, screen } from "@testing-library/react";
import { vi } from "vitest";

import { ChatPanel } from "./ChatPanel";

test("renders the console header and speaker labels in Chinese", () => {
  render(
    <ChatPanel
      draft="你好"
      focusGoalTitle="整理今天的对话记忆"
      focusModeLabel="晨间计划"
      isSending={false}
      latestActionLabel={null}
      messages={[
        { id: "1", role: "user", content: "你好" },
        { id: "2", role: "assistant", content: "我在。" },
      ]}
      modeLabel="运行中"
      onDraftChange={vi.fn()}
      onSend={vi.fn()}
    />,
  );

  expect(screen.getByText("对话")).toBeInTheDocument();
  expect(screen.getByText("当前焦点")).toBeInTheDocument();
  expect(screen.getByText("整理今天的对话记忆")).toBeInTheDocument();
  expect(screen.getByText("你")).toBeInTheDocument();
  expect(screen.getByText("小晏")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "发送" })).toBeInTheDocument();
});

test("disables send while sending or when the draft is empty", () => {
  const onSend = vi.fn();

  const { rerender } = render(
    <ChatPanel
      draft=""
      focusGoalTitle={null}
      focusModeLabel="休眠"
      isSending={false}
      latestActionLabel={null}
      messages={[]}
      modeLabel="休眠中"
      onDraftChange={vi.fn()}
      onSend={onSend}
    />,
  );

  expect(screen.getByRole("button", { name: "发送" })).toBeDisabled();

  rerender(
    <ChatPanel
      draft="你好"
      focusGoalTitle={null}
      focusModeLabel="休眠"
      isSending={true}
      latestActionLabel={null}
      messages={[]}
      modeLabel="休眠中"
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
      focusGoalTitle={null}
      focusModeLabel="常规自主"
      isSending={false}
      latestActionLabel="pwd -> /Users/ldy/Desktop/map/ai"
      messages={[]}
      modeLabel="运行中"
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

test("sends message on Enter key press", () => {
  const onSend = vi.fn();

  render(
    <ChatPanel
      draft="你好"
      focusGoalTitle={null}
      focusModeLabel="常规自主"
      isSending={false}
      latestActionLabel={null}
      messages={[]}
      modeLabel="运行中"
      onDraftChange={vi.fn()}
      onSend={onSend}
    />,
  );

  const textarea = screen.getByLabelText("对话输入");
  fireEvent.keyDown(textarea, { key: "Enter", shiftKey: false });

  expect(onSend).toHaveBeenCalledTimes(1);
});

test("does not send on Shift+Enter", () => {
  const onSend = vi.fn();

  render(
    <ChatPanel
      draft="你好"
      focusGoalTitle={null}
      focusModeLabel="常规自主"
      isSending={false}
      latestActionLabel={null}
      messages={[]}
      modeLabel="运行中"
      onDraftChange={vi.fn()}
      onSend={onSend}
    />,
  );

  const textarea = screen.getByLabelText("对话输入");
  fireEvent.keyDown(textarea, { key: "Enter", shiftKey: true });

  expect(onSend).not.toHaveBeenCalled();
});

test("renders loading state when sending", () => {
  render(
    <ChatPanel
      draft=""
      focusGoalTitle={null}
      focusModeLabel="常规自主"
      isSending={true}
      latestActionLabel={null}
      messages={[]}
      modeLabel="运行中"
      onDraftChange={vi.fn()}
      onSend={vi.fn()}
    />,
  );

  expect(screen.getByText("思考中")).toBeInTheDocument();
});
