import { render, screen } from "@testing-library/react";

import { StatusPanel } from "./StatusPanel";

test("renders her plan for today when a morning plan exists", () => {
  render(
    <StatusPanel
      error=""
      focusGoalTitle="整理今天的对话记忆"
      state={{
        mode: "awake",
        focus_mode: "morning_plan",
        current_thought: "今天先把轮廓理一下。",
        active_goal_ids: ["goal-1"],
        last_action: null,
        self_programming_job: null,
        today_plan: {
          goal_id: "goal-1",
          goal_title: "整理今天的对话记忆",
          steps: [
            { content: "把「整理今天的对话记忆」的轮廓理一下", status: "pending" },
            { content: "开始动手推进", status: "pending" },
          ],
        },
      }}
    />
  );

  expect(screen.getAllByText("今日计划").length).toBeGreaterThanOrEqual(1);
  expect(screen.getByText("当前日程与自我编程状态")).toBeInTheDocument();
  expect(screen.getByText("整理今天的对话记忆")).toBeInTheDocument();
  expect(screen.getAllByText("待处理")).toHaveLength(2);
  expect(screen.getByText("把「整理今天的对话记忆」的轮廓理一下")).toBeInTheDocument();
  expect(screen.getByText("开始动手推进")).toBeInTheDocument();
});


test("renders completed state when today's plan is finished", () => {
  render(
    <StatusPanel
      error=""
      focusGoalTitle="整理今天的对话记忆"
      state={{
        mode: "awake",
        focus_mode: "autonomy",
        current_thought: "今天的计划先收住了。",
        active_goal_ids: ["goal-1"],
        last_action: {
          command: "pwd",
          output: "/Users/ldy/Desktop/map/ai",
        },
        self_programming_job: null,
        today_plan: {
          goal_id: "goal-1",
          goal_title: "整理今天的对话记忆",
          steps: [
            { content: "把「整理今天的对话记忆」的轮廓理一下", status: "completed" },
            { content: "开始动手推进", status: "completed" },
          ],
        },
      }}
    />
  );

  expect(screen.getByText("当前日程与自我编程状态")).toBeInTheDocument();
  expect(screen.getAllByText("已完成").length).toBeGreaterThanOrEqual(1);
  expect(screen.getByText("把「整理今天的对话记忆」的轮廓理一下")).toBeInTheDocument();
  expect(screen.getByText("开始动手推进")).toBeInTheDocument();
});


test("renders self programming progress and verification result", () => {
  render(
    <StatusPanel
      error=""
      state={{
        mode: "awake",
        focus_mode: "self_programming",
        current_thought: "我先停下来修一修自己。",
        active_goal_ids: [],
        last_action: null,
        today_plan: null,
        self_programming_job: {
          id: "job-1",
          reason: "测试失败：状态面板没有展示自我编程状态。",
          target_area: "ui",
          status: "verifying",
          spec: "补上自我编程状态展示。",
          patch_summary: "已修改 apps/desktop/src/components/StatusPanel.tsx",
          red_verification: {
            commands: ["npm test -- --run src/components/StatusPanel.test.tsx"],
            passed: false,
            summary: "1 failed",
          },
          verification: {
            commands: ["npm test -- --run src/components/StatusPanel.test.tsx"],
            passed: true,
            summary: "1 passed",
          },
          touched_files: [
            "apps/desktop/src/components/StatusPanel.tsx",
            "apps/desktop/src/components/StatusPanel.test.tsx",
          ],
        },
      }}
    />
  );

  expect(screen.getAllByText("自我编程").length).toBeGreaterThanOrEqual(1);
  expect(screen.getByText("ui")).toBeInTheDocument();
  expect(screen.getAllByText("验证中").length).toBeGreaterThanOrEqual(1);
  expect(screen.getByText("测试失败：状态面板没有展示自我编程状态。")).toBeInTheDocument();
});
