import { fireEvent, render, screen } from "@testing-library/react";
import { vi } from "vitest";

import { GoalsPanel } from "./GoalsPanel";


test("renders goals and forwards status updates", () => {
  const onUpdateGoalStatus = vi.fn();

  render(
    <GoalsPanel
      goals={[
        {
          id: "goal-1",
          title: "持续理解用户最近在意的话题：星星",
          status: "active",
          chain_id: "chain-1",
          parent_goal_id: "goal-root",
          generation: 1,
        },
      ]}
      onUpdateGoalStatus={onUpdateGoalStatus}
    />
  );

  expect(screen.getByText("持续理解用户最近在意的话题：星星")).toBeInTheDocument();
  expect(screen.getByText("active")).toBeInTheDocument();
  expect(screen.getByText("Chain: chain-1")).toBeInTheDocument();
  expect(screen.getByText("Generation: 1")).toBeInTheDocument();
  expect(screen.getByText("Parent: goal-root")).toBeInTheDocument();

  fireEvent.click(screen.getByText("Pause"));
  fireEvent.click(screen.getByText("Complete"));
  fireEvent.click(screen.getByText("Abandon"));

  expect(onUpdateGoalStatus).toHaveBeenNthCalledWith(1, "goal-1", "paused");
  expect(onUpdateGoalStatus).toHaveBeenNthCalledWith(2, "goal-1", "completed");
  expect(onUpdateGoalStatus).toHaveBeenNthCalledWith(3, "goal-1", "abandoned");
});
