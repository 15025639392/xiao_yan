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

  expect(screen.getByText("目标看板")).toBeInTheDocument();
  expect(screen.getByText("目标链")).toBeInTheDocument();
  expect(screen.getByText("持续理解用户最近在意的话题：星星")).toBeInTheDocument();
  expect(screen.getByText("推进中")).toBeInTheDocument();
  expect(screen.getByText("链路：chain-1")).toBeInTheDocument();
  expect(screen.getByText("第 1 代")).toBeInTheDocument();
  expect(screen.getByText("上级目标：goal-root")).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "暂停" }));
  fireEvent.click(screen.getByRole("button", { name: "完成" }));
  fireEvent.click(screen.getByRole("button", { name: "放弃" }));

  expect(onUpdateGoalStatus).toHaveBeenNthCalledWith(1, "goal-1", "paused");
  expect(onUpdateGoalStatus).toHaveBeenNthCalledWith(2, "goal-1", "completed");
  expect(onUpdateGoalStatus).toHaveBeenNthCalledWith(3, "goal-1", "abandoned");
});


test("renders chained goals as a timeline ordered by generation", () => {
  render(
    <GoalsPanel
      goals={[
        {
          id: "goal-2",
          title: "继续推进：整理今天的对话",
          status: "active",
          chain_id: "chain-1",
          parent_goal_id: "goal-1",
          generation: 1,
        },
        {
          id: "goal-1",
          title: "继续消化自己刚经历的状态：整理今天的对话",
          status: "completed",
          chain_id: "chain-1",
          parent_goal_id: null,
          generation: 0,
        },
      ]}
      onUpdateGoalStatus={vi.fn()}
    />
  );

  expect(screen.getByText("链路 chain-1")).toBeInTheDocument();
  const generationLabels = screen
    .getAllByText(/^第 \d+ 代$/)
    .map((item) => item.textContent);
  expect(generationLabels).toEqual(["第 0 代", "第 1 代"]);
});


test("renders a chain summary with current step and progress", () => {
  render(
    <GoalsPanel
      goals={[
        {
          id: "goal-3",
          title: "准备把新观察写进世界模型",
          status: "paused",
          chain_id: "chain-2",
          parent_goal_id: "goal-2",
          generation: 2,
        },
        {
          id: "goal-1",
          title: "从一次世界事件里提炼方向",
          status: "completed",
          chain_id: "chain-2",
          parent_goal_id: null,
          generation: 0,
        },
        {
          id: "goal-2",
          title: "追踪这条方向在最近对话里的回声",
          status: "active",
          chain_id: "chain-2",
          parent_goal_id: "goal-1",
          generation: 1,
        },
      ]}
      onUpdateGoalStatus={vi.fn()}
    />
  );

  expect(
    screen.getByText(
      "共 3 步，当前推进到第 2 代，状态为已暂停，当前目标是“准备把新观察写进世界模型”",
    ),
  ).toBeInTheDocument();
});


test("prefers an in-progress goal in the summary when generations tie", () => {
  render(
    <GoalsPanel
      goals={[
        {
          id: "goal-2",
          title: "继续沿着这条结论追问",
          status: "active",
          chain_id: "chain-3",
          parent_goal_id: "goal-1",
          generation: 1,
        },
        {
          id: "goal-1",
          title: "把第一次观察收束成结论",
          status: "completed",
          chain_id: "chain-3",
          parent_goal_id: null,
          generation: 1,
        },
      ]}
      onUpdateGoalStatus={vi.fn()}
    />
  );

  expect(
    screen.getByText("共 2 步，当前推进到第 1 代，状态为推进中，当前目标是“继续沿着这条结论追问”"),
  ).toBeInTheDocument();
});

test("renders standalone goals in a separate group with Chinese controls", () => {
  render(
    <GoalsPanel
      goals={[
        {
          id: "goal-1",
          title: "整理今天的世界观察",
          status: "paused",
          generation: 0,
        },
      ]}
      onUpdateGoalStatus={vi.fn()}
    />,
  );

  expect(screen.getByText("独立目标")).toBeInTheDocument();
  expect(screen.getByText("已暂停")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "恢复" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "完成" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "放弃" })).toBeInTheDocument();
});
