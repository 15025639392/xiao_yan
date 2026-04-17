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
      onUpdateGoalStatus={vi.fn()}
    />
  );

  expect(screen.getByText("默认首页只保留核心目标推进")).toBeInTheDocument();
  expect(screen.getByText("把 overview 的目标链路收敛成摘要模式")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "📊 执行统计" })).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "🔧 分解任务" })).not.toBeInTheDocument();
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
