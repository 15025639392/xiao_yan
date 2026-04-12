import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { vi } from "vitest";

import { SessionHistoryPanel } from "./SessionHistoryPanel";
import { createEmptySessionHistoryFilter } from "../../lib/orchestratorWorkbench";

test("session history panel filters and resumes sessions", async () => {
  const onApplyFilter = vi.fn().mockResolvedValue(undefined);
  const onActivateSession = vi.fn().mockResolvedValue(undefined);
  const onDeleteSession = vi.fn().mockResolvedValue(undefined);

  render(
    <SessionHistoryPanel
      viewModel={{
        sessions: [
          {
            session_id: "session-1",
            project_path: "/tmp/demo-project",
            project_name: "demo-project",
            goal: "demo",
            status: "failed",
            plan: null,
            delegates: [],
            coordination: { mode: "failed", priority_score: 1, waiting_reason: "failed" },
            verification: null,
            summary: "failed",
            entered_at: "2026-04-08T12:00:00.000Z",
            updated_at: "2026-04-08T12:10:00.000Z",
          },
        ],
        byStatusCount: {
          draft: 0,
          planning: 0,
          pending_plan_approval: 0,
          dispatching: 0,
          running: 0,
          verifying: 0,
          completed: 0,
          failed: 1,
          cancelled: 0,
        },
      }}
      filter={createEmptySessionHistoryFilter()}
      activeSessionId={"session-1"}
      onFilterChange={vi.fn()}
      onApplyFilter={onApplyFilter}
      onActivateSession={onActivateSession}
      onResumeSession={vi.fn().mockResolvedValue(undefined)}
      onDeleteSession={onDeleteSession}
    />,
  );

  fireEvent.click(screen.getByRole("button", { name: "筛选" }));
  await waitFor(() => {
    expect(onApplyFilter).toHaveBeenCalled();
  });

  fireEvent.click(screen.getByRole("button", { name: "恢复会话" }));
  await waitFor(() => {
    expect(onActivateSession).toHaveBeenCalledWith("session-1");
  });

  fireEvent.click(screen.getByRole("button", { name: "删除会话" }));
  await waitFor(() => {
    expect(onDeleteSession).toHaveBeenCalledWith("session-1");
  });
});
