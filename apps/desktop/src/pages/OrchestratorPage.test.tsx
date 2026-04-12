import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { vi } from "vitest";

import { OrchestratorPage } from "./OrchestratorPage";
import type { OrchestratorPageProps } from "./OrchestratorPage";
import { createEmptySessionHistoryFilter } from "../lib/orchestratorWorkbench";

function buildProps(overrides: Partial<OrchestratorPageProps> = {}): OrchestratorPageProps {
  return {
    sessions: [
      {
        session_id: "session-1",
        project_path: "/tmp/demo-project",
        project_name: "demo-project",
        goal: "进入主控，梳理 Tauri 启动链路",
        status: "running",
        plan: {
          objective: "进入主控，梳理 Tauri 启动链路",
          constraints: [],
          definition_of_done: ["说明入口链路", "给出改造建议"],
          project_snapshot: {
            project_path: "/tmp/demo-project",
            project_name: "demo-project",
            repository_root: "/tmp/demo-project",
            languages: ["TypeScript", "Rust"],
            package_manager: "pnpm",
            framework: "tauri",
            entry_files: ["src/main.ts", "src-tauri/src/main.rs"],
            test_commands: ["pnpm test"],
            build_commands: ["pnpm build"],
            key_directories: ["src", "src-tauri"],
          },
          tasks: [
            {
              task_id: "task-analyze",
              title: "梳理启动链路",
              kind: "analyze",
              scope_paths: ["src", "src-tauri"],
              acceptance_commands: [],
              depends_on: [],
              delegate_target: "codex",
              status: "running",
              delegate_run_id: "run-1",
              engineer_id: 1,
              engineer_label: "工程师1号(codex)",
              assigned_at: "2026-04-08T12:00:00.000Z",
              artifacts: {
                engineer_id: 1,
                engineer_label: "工程师1号(codex)",
                assigned_at: "2026-04-08T12:00:00.000Z",
              },
              result_summary: "工程师1号(codex) 已接单，正在执行。",
            },
          ],
        },
        delegates: [
          {
            task_id: "task-analyze",
            delegate_run_id: "run-1",
            provider: "codex",
            status: "running",
            started_at: "2026-04-08T12:00:00.000Z",
          },
        ],
        coordination: {
          mode: "running",
          priority_score: 101,
          waiting_reason: "正在执行中",
        },
        verification: null,
        summary: "推进中",
        entered_at: "2026-04-08T12:00:00.000Z",
        updated_at: "2026-04-08T12:10:00.000Z",
      },
      {
        session_id: "session-2",
        project_path: "/tmp/demo-project-2",
        project_name: "demo-project-2",
        goal: "进入主控，修复失败任务",
        status: "failed",
        plan: null,
        delegates: [],
        coordination: {
          mode: "failed",
          priority_score: 40,
          waiting_reason: "delegate failed",
          failure_category: "delegate_failure",
        },
        verification: null,
        summary: "delegate failed",
        entered_at: "2026-04-08T13:00:00.000Z",
        updated_at: "2026-04-08T13:10:00.000Z",
      },
    ],
    historySessions: [
      {
        session_id: "session-2",
        project_path: "/tmp/demo-project-2",
        project_name: "demo-project-2",
        goal: "进入主控，修复失败任务",
        status: "failed",
        plan: null,
        delegates: [],
        coordination: {
          mode: "failed",
          priority_score: 40,
          waiting_reason: "delegate failed",
          failure_category: "delegate_failure",
        },
        verification: null,
        summary: "delegate failed",
        entered_at: "2026-04-08T13:00:00.000Z",
        updated_at: "2026-04-08T13:10:00.000Z",
      },
    ],
    scheduler: {
      max_parallel_sessions: 2,
      running_sessions: 1,
      available_slots: 1,
      queued_sessions: 0,
      active_session_id: "session-1",
      running_session_ids: ["session-1"],
      queued_session_ids: [],
      verification_rollup: {
        total_sessions: 2,
        passed_sessions: 0,
        failed_sessions: 1,
        pending_sessions: 1,
      },
      policy_note: "最多并行 2 个项目会话",
    },
    messages: [
      {
        message_id: "msg-1",
        session_id: "session-1",
        role: "assistant",
        state: "completed",
        created_at: "2026-04-08T12:10:00.000Z",
        blocks: [{ type: "markdown", text: "主控计划已经整理好了。" }],
      },
    ],
    workbenchTabs: [
      {
        tab_id: "session-session-1",
        type: "session",
        session_id: "session-1",
      },
    ],
    activeWorkbenchTabId: "session-session-1",
    activeSessionId: "session-1",
    activeProjectPath: "/tmp/demo-project",
    draft: "",
    isSending: false,
    historyFilter: createEmptySessionHistoryFilter(),
    onHistoryFilterChange: vi.fn(),
    onApplyHistoryFilter: vi.fn().mockResolvedValue(undefined),
    onActivateWorkbenchTab: vi.fn(),
    onCloseWorkbenchTab: vi.fn(),
    onCreateBlankTab: vi.fn(),
    onDraftChange: vi.fn(),
    onSendMessage: vi.fn().mockResolvedValue(undefined),
    onActivateSession: vi.fn().mockResolvedValue(undefined),
    onApprovePlan: vi.fn().mockResolvedValue(undefined),
    onRejectPlan: vi.fn().mockResolvedValue(undefined),
    onResumeSession: vi.fn().mockResolvedValue(undefined),
    onCancelSession: vi.fn().mockResolvedValue(undefined),
    onCreateSession: vi.fn().mockResolvedValue(undefined),
    onDeleteSession: vi.fn().mockResolvedValue(undefined),
    onSendQuickMessage: vi.fn().mockResolvedValue(undefined),
    onStopDelegateTask: vi.fn().mockResolvedValue(undefined),
    projectRegistry: {
      projects: [
        {
          path: "/tmp/demo-project",
          name: "demo-project",
          imported_at: "2026-04-08T10:00:00.000Z",
        },
      ],
      active_project_path: "/tmp/demo-project",
    },
    isUpdatingProjects: false,
    projectError: "",
    tauriSupported: true,
    onImportProject: vi.fn().mockResolvedValue(undefined),
    onActivateProject: vi.fn().mockResolvedValue(undefined),
    onRemoveProject: vi.fn().mockResolvedValue(undefined),
    ...overrides,
  };
}

test("renders chat-first orchestrator workspace by default", () => {
  render(<OrchestratorPage {...buildProps()} />);

  expect(screen.getByText("主控计划已经整理好了。", { exact: false })).toBeInTheDocument();
  expect(screen.getByRole("textbox", { name: "主控输入" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "展开高级信息" })).toBeInTheDocument();
  expect(screen.queryByRole("tab", { name: "任务编排" })).not.toBeInTheDocument();
});

test("opens control drawer with auto-focused executor panel when execution is active", () => {
  render(<OrchestratorPage {...buildProps()} />);

  fireEvent.click(screen.getByRole("button", { name: "展开高级信息" }));

  expect(screen.getByText("当前最需要关注")).toBeInTheDocument();
  expect(screen.getByText("执行者")).toBeInTheDocument();
  expect(screen.getByText("执行者 1 位")).toBeInTheDocument();
  expect(screen.queryByRole("tab", { name: "执行者" })).not.toBeInTheDocument();
});

test("forwards stop action from executor panel", async () => {
  const onStopDelegateTask = vi.fn().mockResolvedValue(undefined);
  render(<OrchestratorPage {...buildProps({ onStopDelegateTask })} />);

  fireEvent.click(screen.getByRole("button", { name: "展开高级信息" }));
  fireEvent.click(screen.getByRole("button", { name: "停止任务" }));

  await waitFor(() => {
    expect(onStopDelegateTask).toHaveBeenCalledWith({
      sessionId: "session-1",
      taskId: "task-analyze",
      runId: "run-1",
    });
  });
});

test("applies session history filters", async () => {
  const onApplyHistoryFilter = vi.fn().mockResolvedValue(undefined);
  render(
    <OrchestratorPage
      {...buildProps({
        onApplyHistoryFilter,
        sessions: [
          {
            session_id: "session-2",
            project_path: "/tmp/demo-project-2",
            project_name: "demo-project-2",
            goal: "进入主控，修复失败任务",
            status: "completed",
            plan: null,
            delegates: [],
            coordination: {
              mode: "completed",
              priority_score: 20,
              waiting_reason: "已完成",
            },
            verification: null,
            summary: "完成",
            entered_at: "2026-04-08T13:00:00.000Z",
            updated_at: "2026-04-08T13:10:00.000Z",
          },
        ],
        historySessions: [
          {
            session_id: "session-2",
            project_path: "/tmp/demo-project-2",
            project_name: "demo-project-2",
            goal: "进入主控，修复失败任务",
            status: "completed",
            plan: null,
            delegates: [],
            coordination: {
              mode: "completed",
              priority_score: 20,
              waiting_reason: "已完成",
            },
            verification: null,
            summary: "完成",
            entered_at: "2026-04-08T13:00:00.000Z",
            updated_at: "2026-04-08T13:10:00.000Z",
          },
        ],
        scheduler: {
          max_parallel_sessions: 2,
          running_sessions: 0,
          available_slots: 2,
          queued_sessions: 0,
          active_session_id: "session-2",
          running_session_ids: [],
          queued_session_ids: [],
          verification_rollup: {
            total_sessions: 1,
            passed_sessions: 1,
            failed_sessions: 0,
            pending_sessions: 0,
          },
          policy_note: "最多并行 2 个项目会话",
        },
        workbenchTabs: [
          {
            tab_id: "session-session-2",
            type: "session",
            session_id: "session-2",
          },
        ],
        activeWorkbenchTabId: "session-session-2",
        activeSessionId: "session-2",
      })}
    />,
  );

  fireEvent.click(screen.getByRole("button", { name: "展开高级信息" }));
  fireEvent.click(screen.getByRole("button", { name: "筛选" }));

  await waitFor(() => {
    expect(onApplyHistoryFilter).toHaveBeenCalled();
  });
});

test("does not render clear-console button in simplified header", () => {
  render(<OrchestratorPage {...buildProps()} />);
  expect(screen.queryByRole("button", { name: "清空控制台内容" })).not.toBeInTheDocument();
});
