import { fireEvent, render, screen } from "@testing-library/react";
import { vi } from "vitest";

import { GoalsSummaryPanel } from "./GoalsSummaryPanel";

test("renders overview-safe goals summary without governance actions", () => {
  render(
    <GoalsSummaryPanel
      goals={[
        {
          id: "goal-1",
          title: "把 overview 的目标链路收敛成摘要模式",
          status: "active",
          generation: 0,
        },
      ]}
      focusGoalId="goal-1"
      focusGoalTitle="把 overview 的目标链路收敛成摘要模式"
      focusContext={{
        goal_title: "把 overview 的目标链路收敛成摘要模式",
        source_kind: "goal_chain",
        source_label: "她一直接着往下推进的这条线",
        reason_kind: "goal_chain_continuing",
        reason_label: "这条线已经推到第2步了，还会继续往下走",
        prompt_summary: "当前焦点来自她一直接着往下推进的这条线，之所以还在推进，是因为这条线已经推到第2步了，还会继续往下走。",
      }}
      onUpdateGoalStatus={vi.fn()}
    />
  );

  expect(screen.getByText("默认首页只保留核心目标推进")).toBeInTheDocument();
  expect(screen.getByText("当前焦点正在这里")).toBeInTheDocument();
  expect(screen.getByText("续推中")).toBeInTheDocument();
  expect(screen.getByText("会先盯着这件事，因为这是她一直接着往下推进的这条线。")).toBeInTheDocument();
  expect(screen.getByText("小晏现在主要就在推进这条。")).toBeInTheDocument();
  expect(screen.getAllByText("把 overview 的目标链路收敛成摘要模式").length).toBeGreaterThanOrEqual(2);
  expect(screen.queryByRole("button", { name: "📊 执行统计" })).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "🔧 分解任务" })).not.toBeInTheDocument();
});

test("marks only one active goal as the current focus and keeps the other as parallel", () => {
  render(
    <GoalsSummaryPanel
      goals={[
        {
          id: "goal-1",
          title: "收住当前主线",
          status: "active",
          generation: 1,
        },
        {
          id: "goal-2",
          title: "并行整理别的线索",
          status: "active",
          generation: 0,
        },
      ]}
      focusGoalId="goal-1"
      focusGoalTitle="收住当前主线"
      focusContext={{
        goal_title: "收住当前主线",
        source_kind: "goal_chain",
        source_label: "她一直接着往下推进的这条线",
        reason_kind: "goal_chain_closing",
        reason_label: "这条线已经推到第3步了，现在主要是在收尾",
        prompt_summary: "",
      }}
      onUpdateGoalStatus={vi.fn()}
    />
  );

  expect(screen.getByText("当前焦点")).toBeInTheDocument();
  expect(screen.getByText("并行目标")).toBeInTheDocument();
  expect(screen.getByText("这条也在推进，但小晏现在先在处理「收住当前主线」。")).toBeInTheDocument();
});

test("forwards goal status changes from the summary board", () => {
  const onUpdateGoalStatus = vi.fn();

  render(
    <GoalsSummaryPanel
      goals={[
        {
          id: "goal-1",
          title: "继续推进总览整改",
          status: "active",
          generation: 0,
        },
      ]}
      onUpdateGoalStatus={onUpdateGoalStatus}
    />
  );

  fireEvent.click(screen.getByRole("button", { name: "暂停" }));

  expect(onUpdateGoalStatus).toHaveBeenCalledWith("goal-1", "paused");
});
