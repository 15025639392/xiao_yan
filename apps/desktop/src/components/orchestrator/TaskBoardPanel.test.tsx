import { fireEvent, render, screen } from "@testing-library/react";
import { vi } from "vitest";

import { TaskBoardPanel } from "./TaskBoardPanel";
import type { TaskBoardViewModel } from "../../lib/orchestratorWorkbench";

function buildViewModel(): TaskBoardViewModel {
  return {
    metrics: {
      running: 1,
      queued: 1,
      failed: 1,
      stalled: 0,
      averageReceiptMinutes: 8,
    },
    tasks: [
      {
        sessionId: "session-1",
        taskId: "task-running",
        title: "运行中的任务",
        kind: "implement",
        status: "running",
        engineerId: 1,
        engineerLabel: "工程师1号(codex)",
        assignedAt: "2026-04-12T10:00:00.000Z",
        delegateRunId: "run-1",
        stallLevel: null,
        stallFollowupCommand: null,
        lastStallFollowupAt: null,
        lastIntervenedAt: null,
        interventionSuggestions: [],
        summary: "正在处理中",
        scopePaths: ["src"],
        acceptanceCommands: [],
      },
      {
        sessionId: "session-1",
        taskId: "task-failed",
        title: "失败的任务",
        kind: "fix",
        status: "failed",
        engineerId: 2,
        engineerLabel: "工程师2号(codex)",
        assignedAt: "2026-04-12T10:10:00.000Z",
        delegateRunId: "run-2",
        stallLevel: null,
        stallFollowupCommand: null,
        lastStallFollowupAt: null,
        lastIntervenedAt: null,
        interventionSuggestions: [],
        summary: "需要排障",
        scopePaths: ["src"],
        acceptanceCommands: [],
      },
      {
        sessionId: "session-1",
        taskId: "task-pending",
        title: "待执行任务",
        kind: "analyze",
        status: "pending",
        engineerId: null,
        engineerLabel: null,
        assignedAt: null,
        delegateRunId: null,
        stallLevel: null,
        stallFollowupCommand: null,
        lastStallFollowupAt: null,
        lastIntervenedAt: null,
        interventionSuggestions: [],
        summary: "等待执行",
        scopePaths: ["src"],
        acceptanceCommands: [],
      },
      {
        sessionId: "session-1",
        taskId: "task-succeeded",
        title: "已完成任务",
        kind: "test",
        status: "succeeded",
        engineerId: 1,
        engineerLabel: "工程师1号(codex)",
        assignedAt: "2026-04-12T09:00:00.000Z",
        delegateRunId: null,
        stallLevel: null,
        stallFollowupCommand: null,
        lastStallFollowupAt: null,
        lastIntervenedAt: null,
        interventionSuggestions: [],
        summary: "已完成",
        scopePaths: ["src"],
        acceptanceCommands: [],
      },
    ],
  };
}

test("shows running and failed tasks by default", () => {
  render(<TaskBoardPanel viewModel={buildViewModel()} onSendQuickMessage={vi.fn()} />);

  expect(screen.getByText("运行中的任务")).toBeInTheDocument();
  expect(screen.getByText("失败的任务")).toBeInTheDocument();
  expect(screen.queryByText("待执行任务")).not.toBeInTheDocument();
  expect(screen.queryByText("已完成任务")).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "查看全部任务（4）" })).toBeInTheDocument();
});

test("expands and collapses non-critical tasks", () => {
  render(<TaskBoardPanel viewModel={buildViewModel()} onSendQuickMessage={vi.fn()} />);

  fireEvent.click(screen.getByRole("button", { name: "查看全部任务（4）" }));
  expect(screen.getByText("待执行任务")).toBeInTheDocument();
  expect(screen.getByText("已完成任务")).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "收起非关键任务" }));
  expect(screen.queryByText("待执行任务")).not.toBeInTheDocument();
  expect(screen.queryByText("已完成任务")).not.toBeInTheDocument();
});
