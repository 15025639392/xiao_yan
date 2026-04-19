import { render, screen } from "@testing-library/react";
import { vi } from "vitest";

import { ChatHeader } from "./ChatHeader";

test("renders focus context summary under the current focus title", () => {
  render(
    <ChatHeader
      focusGoalTitle="整理今天的对话记忆"
      focusContext={{
        goal_title: "整理今天的对话记忆",
        source_kind: "user_topic_goal",
        source_label: "刚接住你这轮话题的事",
        reason_kind: "focus_subject_reason",
        reason_label: "今天这条还剩 2 步没做完",
        prompt_summary: "当前焦点来自刚接住你这轮话题的事，之所以还在推进，是因为今天这条还剩 2 步没做完。",
      }}
      focusSubject={{
        kind: "goal",
        title: "整理今天的对话记忆",
        why_now: "我刚把这件事正式接成了当前要持续推进的主线。",
        goal_id: "goal-1",
      }}
      focusEffort={{
        goal_id: "goal-1",
        goal_title: "整理今天的对话记忆",
        why_now: "刚围绕当前这条焦点线完成了一轮对话回应。",
        action_kind: "chat_reply",
        did_what: "先顺着当前焦点把这轮回复接住并说出来了。",
        effect: "用户现在能更明确感到她为什么还在围绕这条线继续。",
        next_hint: "接下来可以继续推进这条线，或根据用户回应调整焦点。",
        created_at: "2026-04-18T06:30:00.000Z",
      }}
      onToggleConfig={vi.fn()}
    />,
  );

  expect(screen.getByText("整理今天的对话记忆")).toBeInTheDocument();
  expect(screen.getByText("用户触发")).toBeInTheDocument();
  expect(screen.getByText("我刚把这件事正式接成了当前要持续推进的主线。")).toBeInTheDocument();
  expect(screen.getByText("刚刚围绕它回应了你: 先顺着当前焦点把这轮回复接住并说出来了。")).toBeInTheDocument();
});
