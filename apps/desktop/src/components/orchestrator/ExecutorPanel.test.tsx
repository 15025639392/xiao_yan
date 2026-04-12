import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { vi } from "vitest";

import { ExecutorPanel } from "./ExecutorPanel";

test("executor stop button transitions from idle to success", async () => {
  const onStopTask = vi.fn().mockResolvedValue(undefined);
  render(
    <ExecutorPanel
      executors={[
        {
          sessionId: "session-1",
          taskId: "task-1",
          taskTitle: "实现功能",
          engineerId: 1,
          engineerLabel: "工程师1号(codex)",
          status: "running",
          runId: "run-1",
          assignedAt: "2026-04-08T12:00:00.000Z",
          stalled: false,
          stallLevel: null,
          followupCommand: "追问工程师1号(codex)卡点并给建议",
          suggestions: [],
          managerSummary: null,
          lastInterventionAt: null,
        },
      ]}
      onSendQuickMessage={vi.fn().mockResolvedValue(undefined)}
      onStopTask={onStopTask}
    />,
  );

  fireEvent.click(screen.getByRole("button", { name: "停止任务" }));
  await waitFor(() => {
    expect(onStopTask).toHaveBeenCalledWith({
      sessionId: "session-1",
      taskId: "task-1",
      runId: "run-1",
    });
  });

  await waitFor(() => {
    expect(screen.getByRole("button", { name: "已停止" })).toBeDisabled();
  });
});
