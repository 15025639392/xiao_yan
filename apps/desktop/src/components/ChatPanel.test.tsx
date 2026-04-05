import { fireEvent, render, screen } from "@testing-library/react";
import { vi } from "vitest";

import { ChatPanel } from "./ChatPanel";

test("renders the chat page with header and messages", () => {
  render(
    <ChatPanel
      draft=""
      focusGoalTitle="整理今天的对话记忆"
      focusModeLabel="晨间计划"
      isSending={false}
      messages={[
        { id: "1", role: "user", content: "你好" },
        { id: "2", role: "assistant", content: "我在。" },
      ]}
      modeLabel="运行中"
      onDraftChange={vi.fn()}
      onSend={vi.fn()}
    />,
  );

  // 标题显示当前目标
  expect(screen.getByText("整理今天的对话记忆")).toBeInTheDocument();
  // 消息内容可见
  expect(screen.getByText("你好")).toBeInTheDocument();
  expect(screen.getByText("我在。")).toBeInTheDocument();
  // 发送按钮存在
  expect(screen.getByLabelText("发送")).toBeInTheDocument();
});

test("disables send while sending or when the draft is empty", () => {
  const onSend = vi.fn();

  const { rerender } = render(
    <ChatPanel
      draft=""
      focusGoalTitle={null}
      focusModeLabel="休眠"
      isSending={false}
      messages={[]}
      modeLabel="休眠中"
      onDraftChange={vi.fn()}
      onSend={onSend}
    />,
  );

  expect(screen.getByLabelText("发送")).toBeDisabled();

  rerender(
    <ChatPanel
      draft="你好"
      focusGoalTitle={null}
      focusModeLabel="休眠"
      isSending={true}
      messages={[]}
      modeLabel="休眠中"
      onDraftChange={vi.fn()}
      onSend={onSend}
    />,
  );

  expect(screen.getByLabelText("发送")).toBeDisabled();
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
      messages={[]}
      modeLabel="运行中"
      onDraftChange={onDraftChange}
      onSend={onSend}
    />,
  );

  fireEvent.change(screen.getByLabelText("对话输入"), {
    target: { value: "晚点再聊" },
  });
  fireEvent.click(screen.getByLabelText("发送"));

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
      messages={[]}
      modeLabel="运行中"
      onDraftChange={vi.fn()}
      onSend={vi.fn()}
    />,
  );

  // 发送按钮应该处于禁用状态
  expect(screen.getByLabelText("发送")).toBeDisabled();
});

test("renders today's plan progress in header", () => {
  render(
    <ChatPanel
      draft=""
      focusGoalTitle="整理今天的对话记忆"
      focusModeLabel="常规自主"
      isSending={false}
      messages={[]}
      modeLabel="运行中"
      todayPlan={{
        goal_id: "goal-1",
        goal_title: "整理今天的对话记忆",
        steps: [
          { content: "回顾昨日对话", status: "completed" },
          { content: "整理关键信息", status: "pending" },
        ],
      }}
      onDraftChange={vi.fn()}
      onSend={vi.fn()}
    />,
  );

  // 今日计划进度显示在头部
  expect(screen.getByText(/今日计划.*1\/2.*完成/)).toBeInTheDocument();
});

test("renders quick actions in empty state", () => {
  render(
    <ChatPanel
      draft=""
      focusGoalTitle={null}
      focusModeLabel="常规自主"
      isSending={false}
      messages={[]}
      modeLabel="运行中"
      onDraftChange={vi.fn()}
      onSend={vi.fn()}
    />,
  );

  // 空状态下显示快捷操作按钮
  expect(screen.getByRole("button", { name: "制定今日计划" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "总结对话" })).toBeInTheDocument();
});

test("quick action buttons populate draft", () => {
  const onDraftChange = vi.fn();

  render(
    <ChatPanel
      draft=""
      focusGoalTitle={null}
      focusModeLabel="常规自主"
      isSending={false}
      messages={[]}
      modeLabel="运行中"
      onDraftChange={onDraftChange}
      onSend={vi.fn()}
    />,
  );

  fireEvent.click(screen.getByRole("button", { name: "制定今日计划" }));
  expect(onDraftChange).toHaveBeenCalledWith("帮我制定今天的计划");
});
