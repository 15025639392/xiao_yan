import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { vi } from "vitest";

import { OrchestratorPage } from "./OrchestratorPage";
import type { OrchestratorPageProps } from "./OrchestratorPage";

function buildProps(overrides: Partial<OrchestratorPageProps> = {}): OrchestratorPageProps {
  return {
    sessions: [
      {
        session_id: "session-1",
        project_path: "/tmp/demo-project",
        project_name: "demo-project",
        goal: "进入主控，梳理 Tauri 启动链路",
        status: "pending_plan_approval",
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
              status: "pending",
            },
          ],
        },
        delegates: [],
        coordination: {
          mode: "idle",
          priority_score: 101,
          waiting_reason: "计划已生成，等待计划级审批。",
        },
        verification: null,
        summary: "等待审批",
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
    scheduler: {
      max_parallel_sessions: 2,
      running_sessions: 0,
      available_slots: 2,
      queued_sessions: 0,
      active_session_id: "session-1",
      running_session_ids: [],
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
        blocks: [
          {
            type: "markdown",
            text: "主控计划已经整理好了。",
          },
          {
            type: "plan_card",
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
                  status: "pending",
                },
              ],
            },
          },
          {
            type: "approval_card",
            summary: "计划待审批",
            details: { status: "pending_plan_approval", can_approve: true },
          },
        ],
      },
    ],
    activeSessionId: "session-1",
    activeProjectPath: "/tmp/demo-project",
    draft: "",
    isSending: false,
    onDraftChange: vi.fn(),
    onSendMessage: vi.fn().mockResolvedValue(undefined),
    onActivateSession: vi.fn().mockResolvedValue(undefined),
    onApprovePlan: vi.fn().mockResolvedValue(undefined),
    onRejectPlan: vi.fn().mockResolvedValue(undefined),
    onResumeSession: vi.fn().mockResolvedValue(undefined),
    onSubmitDirective: vi.fn().mockResolvedValue(undefined),
    onCancelSession: vi.fn().mockResolvedValue(undefined),
    onSendQuickMessage: vi.fn().mockResolvedValue(undefined),
    ...overrides,
  };
}

test("renders lite orchestrator workspace by default", () => {
  render(<OrchestratorPage {...buildProps()} />);

  expect(screen.getByText("主控计划已经整理好了。", { exact: false })).toBeInTheDocument();
  expect(screen.getByText("执行计划")).toBeInTheDocument();
  expect(screen.getAllByText("待审批").length).toBeGreaterThan(0);
  expect(screen.getByRole("textbox", { name: "主控输入" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "展开高级信息" })).toBeInTheDocument();
  expect(screen.queryByRole("tab", { name: "计划" })).not.toBeInTheDocument();
  expect(screen.queryByRole("tab", { name: "会话池" })).not.toBeInTheDocument();
});

test("expands advanced info to show context and side tabs", () => {
  render(<OrchestratorPage {...buildProps()} />);

  fireEvent.click(screen.getByRole("button", { name: "展开高级信息" }));

  expect(screen.getByRole("button", { name: "收起高级信息" })).toBeInTheDocument();
  expect(screen.getByText("当前焦点")).toBeInTheDocument();
  expect(screen.getByRole("tab", { name: "计划" })).toBeInTheDocument();
  expect(screen.getByRole("tab", { name: "会话池" })).toBeInTheDocument();
});

test("forwards approve action from chat-first header", () => {
  const onApprovePlan = vi.fn().mockResolvedValue(undefined);
  render(<OrchestratorPage {...buildProps({ onApprovePlan })} />);

  fireEvent.click(screen.getAllByRole("button", { name: "批准并开工" })[0]);

  expect(onApprovePlan).toHaveBeenCalledWith("session-1");
});

test("submits orchestrator chat input", async () => {
  const onDraftChange = vi.fn();
  const onSendMessage = vi.fn().mockResolvedValue(undefined);
  render(<OrchestratorPage {...buildProps({ draft: "先解释当前推进到哪一步", onDraftChange, onSendMessage })} />);

  fireEvent.click(screen.getByRole("button", { name: "发送主控消息" }));

  await waitFor(() => {
    expect(onSendMessage).toHaveBeenCalled();
  });
});

test("fires inline quick action from message card", async () => {
  const onSendQuickMessage = vi.fn().mockResolvedValue(undefined);
  render(<OrchestratorPage {...buildProps({ onSendQuickMessage })} />);

  fireEvent.click(screen.getByRole("button", { name: "先解释计划" }));

  await waitFor(() => {
    expect(onSendQuickMessage).toHaveBeenCalledWith("先解释一下这份计划为什么这么拆");
  });
});

test("locks inline message quick action while sending", async () => {
  let resolveSend: (() => void) | null = null;
  const sendPromise = new Promise<void>((resolve) => {
    resolveSend = resolve;
  });
  const onSendQuickMessage = vi.fn(() => sendPromise);
  render(<OrchestratorPage {...buildProps({ onSendQuickMessage })} />);

  fireEvent.click(screen.getByRole("button", { name: "先解释计划" }));
  expect(onSendQuickMessage).toHaveBeenCalledTimes(1);
  expect(onSendQuickMessage).toHaveBeenCalledWith("先解释一下这份计划为什么这么拆");
  expect(screen.getByRole("button", { name: "发送中..." })).toBeDisabled();

  fireEvent.click(screen.getByRole("button", { name: "发送中..." }));
  expect(onSendQuickMessage).toHaveBeenCalledTimes(1);

  resolveSend?.();

  await waitFor(() => {
    expect(screen.getByRole("button", { name: "先解释计划" })).not.toBeDisabled();
  });
});

test("fires quick send from preset chips", async () => {
  const onSendQuickMessage = vi.fn().mockResolvedValue(undefined);
  render(<OrchestratorPage {...buildProps({ onSendQuickMessage })} />);

  fireEvent.click(screen.getByRole("button", { name: "批准计划并开工" }));

  await waitFor(() => {
    expect(onSendQuickMessage).toHaveBeenCalledWith("批准计划并开工");
  });
});

test("renders failed task recovery actions inline", async () => {
  const onResumeSession = vi.fn().mockResolvedValue(undefined);
  const onSendQuickMessage = vi.fn().mockResolvedValue(undefined);
  render(
    <OrchestratorPage
      {...buildProps({
        activeSessionId: "session-2",
        messages: [
          {
            message_id: "msg-failed-task",
            session_id: "session-2",
            role: "assistant",
            state: "completed",
            created_at: "2026-04-08T13:10:00.000Z",
            related_task_id: "task-implement",
            blocks: [
              {
                type: "task_card",
                task: {
                  task_id: "task-implement",
                  title: "修复 delegate 失败",
                  kind: "implement",
                  scope_paths: ["apps/desktop"],
                  acceptance_commands: ["pnpm vitest run src/pages/OrchestratorPage.test.tsx"],
                  depends_on: [],
                  delegate_target: "codex",
                  status: "failed",
                  result_summary: "delegate failed",
                  error: "codex did not produce a final output payload",
                },
              },
            ],
          },
        ],
        onResumeSession,
        onSendQuickMessage,
      })}
    />,
  );

  fireEvent.click(screen.getByRole("button", { name: "重派失败环节" }));
  fireEvent.click(screen.getByRole("button", { name: "解释失败原因" }));

  await waitFor(() => {
    expect(onResumeSession).toHaveBeenCalledWith("session-2");
    expect(onSendQuickMessage).toHaveBeenCalledWith("解释一下任务「修复 delegate 失败」为什么失败，以及下一步建议");
  });
});

test("renders dispatching live status with skeleton feedback", () => {
  render(
    <OrchestratorPage
      {...buildProps({
        messages: [],
        sessions: [
          {
            ...buildProps().sessions[0],
            status: "dispatching",
            summary: "正在派发 analyze 与 implement 任务",
            coordination: {
              mode: "ready",
              priority_score: 101,
              waiting_reason: "正在把可执行任务分配给 delegate。",
              dispatch_slot: 1,
            },
          },
          buildProps().sessions[1],
        ],
      })}
    />,
  );

  expect(screen.getByText("正在派发任务")).toBeInTheDocument();
  expect(screen.getByText("整理本轮可执行任务")).toBeInTheDocument();
  expect(screen.getByText("等待 Codex delegate 接管")).toBeInTheDocument();
});

test("renders verifying live status with acceptance skeleton feedback", () => {
  render(
    <OrchestratorPage
      {...buildProps({
        messages: [],
        sessions: [
          {
            ...buildProps().sessions[0],
            status: "verifying",
            summary: "正在统一验收当前计划",
            coordination: {
              mode: "verifying",
              priority_score: 101,
              waiting_reason: "统一验收已开始，正在执行计划内命令。",
              dispatch_slot: 1,
            },
          },
          buildProps().sessions[1],
        ],
      })}
    />,
  );

  expect(screen.getByText("正在统一验收")).toBeInTheDocument();
  expect(screen.getByText("执行计划内验收命令")).toBeInTheDocument();
  expect(screen.getByText("准备最终摘要")).toBeInTheDocument();
});

test("renders preempted live status and can jump to blocking session", async () => {
  let resolveActivate: (() => void) | null = null;
  const activatePromise = new Promise<void>((resolve) => {
    resolveActivate = resolve;
  });
  const onActivateSession = vi.fn(() => activatePromise);
  render(
    <OrchestratorPage
      {...buildProps({
        activeSessionId: "session-1",
        onActivateSession,
        sessions: [
          {
            ...buildProps().sessions[0],
            status: "dispatching",
            coordination: {
              mode: "preempted",
              priority_score: 20,
              waiting_reason: "当前会话被更高优先级项目抢占，等待执行槽位释放。",
              queue_position: 2,
              preempted_by_session_id: "session-2",
            },
          },
          buildProps().sessions[1],
        ],
      })}
    />,
  );

  const liveStatus = within(screen.getByLabelText("主控实时状态"));
  expect(liveStatus.getByText("当前会话暂未占用执行槽位")).toBeInTheDocument();
  expect(liveStatus.getByText("队列位置 #2")).toBeInTheDocument();
  expect(liveStatus.getByText("预计等待原因")).toBeInTheDocument();
  expect(liveStatus.getAllByText("当前会话被更高优先级项目抢占，等待执行槽位释放。").length).toBeGreaterThan(0);
  expect(liveStatus.getByText("恢复后优先执行")).toBeInTheDocument();
  expect(liveStatus.getByText("ANALYZE · 梳理启动链路")).toBeInTheDocument();

  fireEvent.click(liveStatus.getByRole("button", { name: "查看抢占会话" }));
  expect(onActivateSession).toHaveBeenCalledTimes(1);
  expect(onActivateSession).toHaveBeenCalledWith("session-2");
  expect(liveStatus.getByRole("button", { name: "切换中..." })).toBeDisabled();

  fireEvent.click(liveStatus.getByRole("button", { name: "切换中..." }));
  expect(onActivateSession).toHaveBeenCalledTimes(1);

  resolveActivate?.();

  await waitFor(() => {
    expect(liveStatus.getByRole("button", { name: "查看抢占会话" })).not.toBeDisabled();
  });
});

test("renders queued live status with next step preview", async () => {
  let resolveSend: (() => void) | null = null;
  const sendPromise = new Promise<void>((resolve) => {
    resolveSend = resolve;
  });
  const onSendQuickMessage = vi.fn(() => sendPromise);
  render(
    <OrchestratorPage
      {...buildProps({
        messages: [],
        onSendQuickMessage,
        sessions: [
          {
            ...buildProps().sessions[0],
            status: "dispatching",
            coordination: {
              mode: "queued",
              priority_score: 55,
              waiting_reason: "当前并行上限已满，需要等待其他项目释放执行槽位。",
              queue_position: 3,
            },
          },
          buildProps().sessions[1],
        ],
      })}
    />,
  );

  const liveStatus = within(screen.getByLabelText("主控实时状态"));
  expect(liveStatus.getByText("当前会话正在队列中等待")).toBeInTheDocument();
  expect(liveStatus.getByText("队列位置 #3")).toBeInTheDocument();
  expect(liveStatus.getByText("预计等待原因")).toBeInTheDocument();
  expect(liveStatus.getAllByText("当前并行上限已满，需要等待其他项目释放执行槽位。").length).toBeGreaterThan(0);
  expect(liveStatus.getByText("恢复后优先执行")).toBeInTheDocument();
  expect(liveStatus.getByText("ANALYZE · 梳理启动链路")).toBeInTheDocument();

  fireEvent.click(liveStatus.getByRole("button", { name: "继续推进这个任务" }));
  expect(onSendQuickMessage).toHaveBeenCalledTimes(1);
  expect(onSendQuickMessage).toHaveBeenCalledWith("继续推进任务「梳理启动链路」，并告诉我你准备怎么做");
  expect(liveStatus.getByRole("button", { name: "推进中..." })).toBeDisabled();

  fireEvent.click(liveStatus.getByRole("button", { name: "推进中..." }));
  expect(onSendQuickMessage).toHaveBeenCalledTimes(1);

  resolveSend?.();

  await waitFor(() => {
    expect(liveStatus.getByRole("button", { name: "继续推进这个任务" })).not.toBeDisabled();
  });
});

test("switches to session pool and activates another session", async () => {
  const onActivateSession = vi.fn().mockResolvedValue(undefined);
  render(<OrchestratorPage {...buildProps({ onActivateSession })} />);

  fireEvent.click(screen.getByRole("button", { name: "展开高级信息" }));
  fireEvent.click(screen.getByRole("tab", { name: "会话池" }));
  fireEvent.click(screen.getByRole("button", { name: /demo-project-2/ }));

  await waitFor(() => {
    expect(onActivateSession).toHaveBeenCalledWith("session-2");
  });
});

test("renders empty state before entering orchestrator", () => {
  render(
    <OrchestratorPage
      {...buildProps({
        sessions: [],
        messages: [],
        activeSessionId: null,
        activeProjectPath: null,
      })}
    />,
  );

  expect(screen.getByText("等待显式进入主控模式")).toBeInTheDocument();
});
