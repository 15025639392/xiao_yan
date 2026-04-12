import type { OrchestratorSchedulerSnapshot, OrchestratorSession, OrchestratorTask } from "./api";

export type SessionHistoryFilter = {
  status: OrchestratorSession["status"][];
  project: string;
  from: string;
  to: string;
  keyword: string;
};

export type TaskBoardItem = {
  sessionId: string;
  taskId: string;
  title: string;
  kind: OrchestratorTask["kind"];
  status: OrchestratorTask["status"];
  engineerId: number | null;
  engineerLabel: string | null;
  assignedAt: string | null;
  delegateRunId: string | null;
  stallLevel: string | null;
  stallFollowupCommand: string | null;
  lastStallFollowupAt: string | null;
  lastIntervenedAt: string | null;
  interventionSuggestions: string[];
  summary: string;
  scopePaths: string[];
  acceptanceCommands: string[];
};

export type TaskBoardViewModel = {
  metrics: {
    running: number;
    queued: number;
    failed: number;
    stalled: number;
    averageReceiptMinutes: number;
  };
  tasks: TaskBoardItem[];
};

export type ExecutorViewModel = {
  sessionId: string;
  taskId: string;
  taskTitle: string;
  engineerId: number;
  engineerLabel: string;
  status: OrchestratorTask["status"];
  runId: string | null;
  assignedAt: string | null;
  stalled: boolean;
  stallLevel: string | null;
  followupCommand: string;
  suggestions: string[];
  managerSummary: string | null;
  lastInterventionAt: string | null;
};

export type SessionHubViewModel = {
  sessions: OrchestratorSession[];
  byStatusCount: Record<OrchestratorSession["status"], number>;
};

export type ChatContextViewModel = {
  sessionId: string | null;
  projectName: string;
  goal: string;
  waitingReason: string;
};

export type WorkbenchViewModel = {
  chatContext: ChatContextViewModel;
  taskBoard: TaskBoardViewModel;
  executors: ExecutorViewModel[];
  sessionHub: SessionHubViewModel;
};

type BuildWorkbenchInput = {
  sessions: OrchestratorSession[];
  activeSessionId: string | null;
  scheduler: OrchestratorSchedulerSnapshot;
  historySessions?: OrchestratorSession[];
};

const EMPTY_HISTORY_STATUS_COUNT: Record<OrchestratorSession["status"], number> = {
  draft: 0,
  planning: 0,
  pending_plan_approval: 0,
  dispatching: 0,
  running: 0,
  verifying: 0,
  completed: 0,
  failed: 0,
  cancelled: 0,
};

export function createEmptySessionHistoryFilter(): SessionHistoryFilter {
  return {
    status: [],
    project: "",
    from: "",
    to: "",
    keyword: "",
  };
}

export function buildWorkbenchViewModel(input: BuildWorkbenchInput): WorkbenchViewModel {
  const activeSession =
    input.sessions.find((session) => session.session_id === input.activeSessionId) ?? input.sessions[0] ?? null;
  const boardTasks = activeSession ? toTaskBoardItems(activeSession) : [];

  const receiptDurations: number[] = [];
  for (const task of boardTasks) {
    if (!["succeeded", "failed", "cancelled"].includes(task.status)) {
      continue;
    }
    if (!task.assignedAt) {
      continue;
    }
    const assignedAt = Date.parse(task.assignedAt);
    const sessionUpdatedAt = activeSession ? Date.parse(activeSession.updated_at) : Number.NaN;
    if (Number.isNaN(assignedAt) || Number.isNaN(sessionUpdatedAt) || sessionUpdatedAt <= assignedAt) {
      continue;
    }
    receiptDurations.push((sessionUpdatedAt - assignedAt) / 60000);
  }

  const averageReceiptMinutes =
    receiptDurations.length === 0
      ? 0
      : Math.round(receiptDurations.reduce((sum, value) => sum + value, 0) / receiptDurations.length);

  const tasks = [...boardTasks].sort((left, right) => {
    const leftPriority = taskStatusPriority(left.status);
    const rightPriority = taskStatusPriority(right.status);
    if (leftPriority !== rightPriority) {
      return leftPriority - rightPriority;
    }
    return left.title.localeCompare(right.title, "zh-Hans-CN");
  });

  const taskBoard: TaskBoardViewModel = {
    metrics: {
      running: tasks.filter((task) => task.status === "running").length,
      queued: tasks.filter((task) => task.status === "pending" || task.status === "queued").length,
      failed: tasks.filter((task) => task.status === "failed").length,
      stalled: tasks.filter((task) => Boolean(task.stallLevel)).length,
      averageReceiptMinutes,
    },
    tasks,
  };

  const executors = toExecutors(tasks);
  const historySource = input.historySessions ?? input.sessions;
  const byStatusCount = { ...EMPTY_HISTORY_STATUS_COUNT };
  for (const session of historySource) {
    byStatusCount[session.status] += 1;
  }

  const sessionHub: SessionHubViewModel = {
    sessions: [...historySource].sort(
      (left, right) => new Date(right.updated_at).getTime() - new Date(left.updated_at).getTime(),
    ),
    byStatusCount,
  };

  return {
    chatContext: {
      sessionId: activeSession?.session_id ?? null,
      projectName: activeSession?.project_name ?? "未选择会话",
      goal: activeSession?.goal ?? "等待主控任务",
      waitingReason: activeSession?.coordination?.waiting_reason ?? "主控已就绪",
    },
    taskBoard,
    executors,
    sessionHub,
  };
}

function taskStatusPriority(status: OrchestratorTask["status"]): number {
  if (status === "running") {
    return 0;
  }
  if (status === "failed") {
    return 1;
  }
  if (status === "queued" || status === "pending") {
    return 2;
  }
  if (status === "succeeded") {
    return 3;
  }
  return 4;
}

function toTaskBoardItems(session: OrchestratorSession): TaskBoardItem[] {
  const tasks = session.plan?.tasks ?? [];
  return tasks.map((task) => {
    const suggestionsFromFollowup = Array.isArray(task.stall_followup?.suggestions)
      ? task.stall_followup.suggestions.filter((item): item is string => typeof item === "string" && item.trim().length > 0)
      : [];
    const suggestionsFromTask = Array.isArray(task.intervention_suggestions)
      ? task.intervention_suggestions.filter((item) => item.trim().length > 0)
      : [];

    return {
      sessionId: session.session_id,
      taskId: task.task_id,
      title: task.title,
      kind: task.kind,
      status: task.status,
      engineerId: typeof task.engineer_id === "number" ? task.engineer_id : null,
      engineerLabel: typeof task.engineer_label === "string" ? task.engineer_label : null,
      assignedAt: typeof task.assigned_at === "string" ? task.assigned_at : null,
      delegateRunId: typeof task.delegate_run_id === "string" ? task.delegate_run_id : null,
      stallLevel: typeof task.stall_level === "string" ? task.stall_level : null,
      stallFollowupCommand:
        typeof task.stall_followup?.followup_command === "string" ? task.stall_followup.followup_command : null,
      lastStallFollowupAt:
        typeof task.last_stall_followup_at === "string" ? task.last_stall_followup_at : null,
      lastIntervenedAt:
        typeof task.last_intervened_at === "string"
          ? task.last_intervened_at
          : typeof task.last_stall_followup_at === "string"
            ? task.last_stall_followup_at
            : null,
      interventionSuggestions:
        suggestionsFromTask.length > 0 ? suggestionsFromTask : suggestionsFromFollowup,
      summary: task.result_summary || task.error || "等待执行中",
      scopePaths: [...task.scope_paths],
      acceptanceCommands: [...task.acceptance_commands],
    };
  });
}

function toExecutors(tasks: TaskBoardItem[]): ExecutorViewModel[] {
  const result: ExecutorViewModel[] = [];
  for (const task of tasks) {
    const hasEngineer = typeof task.engineerId === "number" && task.engineerId > 0;
    if (!hasEngineer) {
      continue;
    }

    const suggestions =
      task.interventionSuggestions.length > 0
        ? task.interventionSuggestions
        : extractSuggestionsFromTask(task);
    const fallbackCommand = task.engineerLabel
      ? `追问${task.engineerLabel}卡点并给建议`
      : `追问任务「${task.title}」卡点并给建议`;

    result.push({
      sessionId: task.sessionId,
      taskId: task.taskId,
      taskTitle: task.title,
      engineerId: task.engineerId ?? 1,
      engineerLabel: task.engineerLabel ?? `工程师${task.engineerId ?? 1}号(codex)`,
      status: task.status,
      runId: task.delegateRunId,
      assignedAt: task.assignedAt,
      stalled: Boolean(task.stallLevel),
      stallLevel: task.stallLevel,
      followupCommand: task.stallFollowupCommand || fallbackCommand,
      suggestions,
      managerSummary: task.stallLevel ? task.summary : null,
      lastInterventionAt: task.lastIntervenedAt,
    });
  }

  return result.sort((left, right) => {
    const leftPriority = executorStatusPriority(left.status);
    const rightPriority = executorStatusPriority(right.status);
    if (leftPriority !== rightPriority) {
      return leftPriority - rightPriority;
    }
    return left.engineerId - right.engineerId;
  });
}

function executorStatusPriority(status: OrchestratorTask["status"]): number {
  if (status === "running") {
    return 0;
  }
  if (status === "failed") {
    return 1;
  }
  if (status === "queued" || status === "pending") {
    return 2;
  }
  return 3;
}

function extractSuggestionsFromTask(task: TaskBoardItem): string[] {
  if (!task.summary) {
    return [];
  }
  const delimiters = /[；。\n]/;
  const rawParts = task.summary
    .split(delimiters)
    .map((item) => item.trim())
    .filter((item) => item.length > 0);
  return rawParts.slice(0, 3);
}
