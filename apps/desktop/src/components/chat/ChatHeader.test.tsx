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
        reason_kind: "today_plan_pending",
        reason_label: "今天这条还剩 2 步没做完",
        prompt_summary: "当前焦点来自刚接住你这轮话题的事，之所以还在推进，是因为今天这条还剩 2 步没做完。",
      }}
      focusTransitionHint="焦点刚切到「整理今天的对话记忆」，因为它直接接住了你刚才这轮话题。"
      onToggleConfig={vi.fn()}
    />,
  );

  expect(screen.getByText("整理今天的对话记忆")).toBeInTheDocument();
  expect(screen.getByText("用户触发")).toBeInTheDocument();
  expect(screen.getByText("会先盯着这件事，因为这是刚接住你这轮话题的事。")).toBeInTheDocument();
  expect(screen.getByText("现在还在继续推进，因为今天这条还剩 2 步没做完。")).toBeInTheDocument();
  expect(screen.getByText("焦点刚切到「整理今天的对话记忆」，因为它直接接住了你刚才这轮话题。")).toBeInTheDocument();
});
