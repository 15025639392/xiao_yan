import { describe, expect, test } from "vitest";

import { buildWorkbenchViewModel, createEmptySessionHistoryFilter } from "./orchestratorWorkbench";
import type { OrchestratorSchedulerSnapshot, OrchestratorSession } from "./api";

const scheduler: OrchestratorSchedulerSnapshot = {
  max_parallel_sessions: 2,
  running_sessions: 1,
  available_slots: 1,
  queued_sessions: 0,
  active_session_id: "session-1",
  running_session_ids: ["session-1"],
  queued_session_ids: [],
  verification_rollup: {
    total_sessions: 1,
    passed_sessions: 0,
    failed_sessions: 0,
    pending_sessions: 1,
  },
  policy_note: null,
};

const runningSession: OrchestratorSession = {
  session_id: "session-1",
  project_path: "/tmp/demo-project",
  project_name: "demo-project",
  goal: "demo",
  status: "running",
  plan: {
    objective: "demo",
    constraints: [],
    definition_of_done: [],
    project_snapshot: {
      project_path: "/tmp/demo-project",
      project_name: "demo-project",
      repository_root: "/tmp/demo-project",
      languages: ["TypeScript"],
      package_manager: "pnpm",
      framework: "vite",
      entry_files: ["src/main.ts"],
      test_commands: ["pnpm test"],
      build_commands: ["pnpm build"],
      key_directories: ["src"],
    },
    tasks: [
      {
        task_id: "task-1",
        title: "实现功能",
        kind: "implement",
        scope_paths: ["src"],
        acceptance_commands: [],
        depends_on: [],
        delegate_target: "codex",
        status: "running",
        delegate_run_id: "run-1",
        engineer_id: 1,
        engineer_label: "工程师1号(codex)",
        assigned_at: "2026-04-08T12:00:00.000Z",
        stall_level: "soft_ping",
        stall_followup: {
          level: "soft_ping",
          followup_command: "追问工程师1号(codex)卡点并给建议",
          suggestions: ["先给出失败命令和错误摘要。"],
        },
        intervention_suggestions: ["先给出失败命令和错误摘要。"],
        artifacts: {
          engineer_id: 1,
          engineer_label: "工程师1号(codex)",
          assigned_at: "2026-04-08T12:00:00.000Z",
          stall_level: "soft_ping",
          stall_followup: {
            followup_command: "追问工程师1号(codex)卡点并给建议",
          },
        },
        result_summary: "执行中",
      },
    ],
  },
  delegates: [
    {
      task_id: "task-1",
      delegate_run_id: "run-1",
      provider: "codex",
      status: "running",
      started_at: "2026-04-08T12:00:00.000Z",
    },
  ],
  coordination: {
    mode: "running",
    priority_score: 1,
    waiting_reason: "执行中",
  },
  verification: null,
  summary: "执行中",
  entered_at: "2026-04-08T12:00:00.000Z",
  updated_at: "2026-04-08T13:00:00.000Z",
};

describe("orchestratorWorkbench", () => {
  test("creates default empty history filter", () => {
    expect(createEmptySessionHistoryFilter()).toEqual({
      status: [],
      project: "",
      from: "",
      to: "",
      keyword: "",
    });
  });

  test("maps sessions into task board and executor view models", () => {
    const vm = buildWorkbenchViewModel({
      sessions: [runningSession],
      activeSessionId: "session-1",
      scheduler,
      historySessions: [runningSession],
    });

    expect(vm.taskBoard.metrics.running).toBe(1);
    expect(vm.taskBoard.metrics.stalled).toBe(1);
    expect(vm.taskBoard.tasks[0]?.taskId).toBe("task-1");
    expect(vm.executors[0]?.engineerLabel).toBe("工程师1号(codex)");
    expect(vm.executors[0]?.followupCommand).toContain("追问工程师1号");
    expect(vm.sessionHub.byStatusCount.running).toBe(1);
  });

  test("does not rely on legacy artifacts-only executor fields", () => {
    const legacySession: OrchestratorSession = {
      ...runningSession,
      plan: {
        ...runningSession.plan!,
        tasks: runningSession.plan!.tasks.map((task) => ({
          ...task,
          engineer_id: null,
          engineer_label: null,
          assigned_at: null,
          stall_level: null,
          stall_followup: null,
          last_stall_followup_at: null,
          last_intervened_at: null,
          intervention_suggestions: [],
        })),
      },
    };

    const vm = buildWorkbenchViewModel({
      sessions: [legacySession],
      activeSessionId: "session-1",
      scheduler,
      historySessions: [legacySession],
    });

    expect(vm.executors).toHaveLength(0);
  });
});
