export type TodayPlanStep = {
  content: string;
  status: "pending" | "completed";
  kind?: "reflect" | "action";
  command?: string | null;
};

export type TodayPlan = {
  goal_id: string;
  goal_title: string;
  steps: TodayPlanStep[];
};

export type EditKind = "replace" | "create" | "insert";

export type SelfProgrammingEdit = {
  file_path: string;
  search_text?: string;
  replace_text?: string;
  kind: EditKind;
  insert_after?: string | null;
  file_content?: string | null;
};

export type SelfProgrammingVerification = {
  commands: string[];
  passed: boolean;
  summary?: string | null;
};

export type SelfProgrammingJob = {
  id: string;
  reason: string;
  reason_statement?: string | null;
  direction_statement?: string | null;
  target_area: string;
  status:
    | "drafted"
    | "pending_start_approval"
    | "queued"
    | "running"
    | "completed"
    | "frozen"
    | "pending"
    | "diagnosing"
    | "patching"
    | "pending_approval"
    | "verifying"
    | "applied"
    | "failed"
    | "rejected";
  spec: string;
  patch_summary?: string | null;
  red_verification?: SelfProgrammingVerification | null;
  verification?: SelfProgrammingVerification | null;
  edits?: SelfProgrammingEdit[];
  test_edits?: SelfProgrammingEdit[];
  touched_files?: string[];
  cooldown_until?: string | null;

  // Git 执行信息
  branch_name?: string | null;
  commit_hash?: string | null;
  commit_message?: string | null;
  candidate_label?: string | null;

  // 预检与冲突信息
  sandbox_prechecked?: boolean;
  sandbox_result?: string | null;
  conflict_severity?: string;
  conflict_details?: string | null;

  // 验证与回滚信息
  health_score?: number | null;
  health_grade?: string | null;
  rollback_info?: string | null;
  snapshot_taken?: boolean;

  // 审批信息
  approval_requested_at?: string | null;
  approval_edits_summary?: string | null;
  approval_reason?: string | null;

  // 开工审批信息
  start_approval_reason?: string | null;
  start_approved_by?: string | null;
  start_approved_at?: string | null;

  // 拒绝审计
  rejection_phase?: "start" | "promotion" | null;
  rejection_reason?: string | null;
  rejected_by?: string | null;
  rejected_at?: string | null;

  // 冷却快照
  cooldown_policy_snapshot?: {
    hard_failure_minutes: number;
    proactive_minutes: number;
  } | null;
};

// 自我编程历史记录
export type SelfProgrammingHistoryEntry = {
  job_id: string;
  target_area: string;
  reason: string;
  reason_statement?: string | null;
  direction_statement?: string | null;
  status: string;
  outcome: string;
  touched_files: string[];
  created_at: string;
  completed_at?: string | null;
  health_score?: number | null;
  had_rollback?: boolean;
  rejection_phase?: "start" | "promotion" | null;
  rejection_reason?: string | null;
  start_approved_at?: string | null;
  approved_at?: string | null;
};

export type SelfProgrammingRuntimeConfig = {
  hard_failure_cooldown_minutes: number;
  proactive_cooldown_minutes: number;
};

export type DelegateCommandResult = {
  command: string;
  success: boolean;
  exit_code?: number | null;
  stdout?: string | null;
  stderr?: string | null;
  duration_ms?: number | null;
};

export type ProjectSnapshot = {
  project_path: string;
  project_name: string;
  repository_root: string;
  languages: string[];
  package_manager?: string | null;
  framework?: string | null;
  entry_files: string[];
  test_commands: string[];
  build_commands: string[];
  key_directories: string[];
};

export type OrchestratorDelegateRequest = {
  objective: string;
  project_path: string;
  scope_paths: string[];
  forbidden_paths: string[];
  acceptance_commands: string[];
  output_schema: Record<string, unknown>;
};

export type OrchestratorDelegateDebugInfo = {
  stderr_excerpt?: string | null;
  last_jsonl_event?: Record<string, unknown> | null;
};

export type OrchestratorDelegateResult = {
  status: "succeeded" | "failed" | string;
  summary?: string | null;
  changed_files: string[];
  command_results: DelegateCommandResult[];
  followup_needed: string[];
  error?: string | null;
  debug?: OrchestratorDelegateDebugInfo | null;
};

export type OrchestratorTask = {
  task_id: string;
  title: string;
  kind: "analyze" | "implement" | "test" | "verify" | "summarize";
  scope_paths: string[];
  acceptance_commands: string[];
  depends_on: string[];
  delegate_target: "codex" | string;
  status: "pending" | "queued" | "running" | "succeeded" | "failed" | "cancelled";
  result_summary?: string | null;
  artifacts?: Record<string, unknown>;
  delegate_run_id?: string | null;
  assignment_source?: string | null;
  assignment_directive?: string | null;
  assignment_requested_objective?: string | null;
  assignment_scope_override?: string[] | null;
  assignment_resolved_scope_override?: string[] | null;
  assignment_acceptance_override?: string[] | null;
  assignment_priority_override?: number | null;
  engineer_id?: number | null;
  engineer_label?: string | null;
  assigned_at?: string | null;
  stall_level?: string | null;
  stall_followup?: {
    level?: string | null;
    elapsed_minutes?: number | null;
    manager_summary?: string | null;
    engineer_prompt?: string | null;
    suggestions?: string[];
    followup_command?: string | null;
  } | null;
  last_stall_followup_at?: string | null;
  last_intervened_at?: string | null;
  intervention_suggestions?: string[];
  error?: string | null;
};

export type OrchestratorPlan = {
  objective: string;
  constraints: string[];
  definition_of_done: string[];
  project_snapshot: ProjectSnapshot;
  tasks: OrchestratorTask[];
};

export type OrchestratorVerification = {
  commands: string[];
  command_results: DelegateCommandResult[];
  passed: boolean;
  summary?: string | null;
};

export type OrchestratorMessageBlock = {
  type:
    | "markdown"
    | "plan_card"
    | "approval_card"
    | "task_card"
    | "directive_card"
    | "verification_card"
    | "summary_card"
    | "session_status_card"
    | string;
  text?: string | null;
  plan?: OrchestratorPlan | null;
  task?: OrchestratorTask | null;
  verification?: OrchestratorVerification | null;
  session?: OrchestratorSession | null;
  summary?: string | null;
  details?: Record<string, unknown>;
};

export type OrchestratorMessage = {
  message_id: string;
  session_id: string;
  role: "user" | "assistant" | "system";
  blocks: OrchestratorMessageBlock[];
  state?: "streaming" | "completed" | "failed";
  created_at: string;
  related_task_id?: string | null;
};

export type OrchestratorChatSubmissionResult = {
  session_id: string;
  assistant_message_id: string;
};

export type OrchestratorConsoleCommandRequest = {
  message: string;
  session_id?: string | null;
  project_path?: string | null;
};

export type OrchestratorConsoleCommandResponse = {
  session: OrchestratorSession;
  assistant_message_id: string;
  created_session: boolean;
};

export type OrchestratorMessagesDeleteResponse = {
  session_id: string;
  deleted_count: number;
};

export type OrchestratorBlankTab = {
  tab_id: string;
  type: "blank";
};

export type OrchestratorSessionTab = {
  tab_id: string;
  type: "session";
  session_id: string;
};

export type WorkbenchTab = OrchestratorBlankTab | OrchestratorSessionTab;

export type OrchestratorSessionDeleteResponse = {
  session_id: string;
  deleted: boolean;
  cleared_messages: number;
};

export type OrchestratorDelegateRun = {
  task_id: string;
  delegate_run_id: string;
  provider: string;
  status: string;
  started_at: string;
  completed_at?: string | null;
};

export type OrchestratorDelegateStopRequest = {
  session_id: string;
  task_id: string;
  delegate_run_id: string;
  reason?: string | null;
};

export type OrchestratorSessionCoordination = {
  mode: "idle" | "ready" | "running" | "queued" | "preempted" | "verifying" | "completed" | "failed" | "cancelled";
  priority_score: number;
  queue_position?: number | null;
  waiting_reason?: string | null;
  failure_category?: "delegate_failure" | "verification_failure" | "policy_violation" | null;
  preempted_by_session_id?: string | null;
  dispatch_slot?: number | null;
};

export type OrchestratorSession = {
  session_id: string;
  project_path: string;
  project_name: string;
  goal: string;
  priority_bias?: number;
  status:
    | "draft"
    | "planning"
    | "pending_plan_approval"
    | "dispatching"
    | "running"
    | "verifying"
    | "completed"
    | "failed"
    | "cancelled";
  plan?: OrchestratorPlan | null;
  delegates: OrchestratorDelegateRun[];
  coordination?: OrchestratorSessionCoordination | null;
  verification?: OrchestratorVerification | null;
  summary?: string | null;
  entered_at: string;
  updated_at: string;
};

export type OrchestratorSessionListFilters = {
  status?: OrchestratorSession["status"][];
  project?: string;
  from?: string;
  to?: string;
  keyword?: string;
};

export type OrchestratorVerificationRollup = {
  total_sessions: number;
  passed_sessions: number;
  failed_sessions: number;
  pending_sessions: number;
};

export type OrchestratorSchedulerSnapshot = {
  max_parallel_sessions: number;
  running_sessions: number;
  available_slots: number;
  queued_sessions: number;
  active_session_id?: string | null;
  running_session_ids: string[];
  queued_session_ids: string[];
  verification_rollup: OrchestratorVerificationRollup;
  policy_note?: string | null;
};

export type GoalAdmissionRuntimeConfig = {
  stability_warning_rate: number;
  stability_danger_rate: number;
};

export type GoalAdmissionConfigHistoryEntry = {
  revision: number;
  source: "bootstrap" | "api_update" | "rollback" | string;
  stability_warning_rate: number;
  stability_danger_rate: number;
  created_at: string;
  rolled_back_from_revision?: number | null;
};

export type GoalAdmissionConfigHistoryResponse = {
  items: GoalAdmissionConfigHistoryEntry[];
};

export type GoalAdmissionConfigRollbackResponse = GoalAdmissionRuntimeConfig & {
  revision: number;
  rolled_back_from_revision: number;
};

export type BeingState = {
  mode: "awake" | "sleeping";
  focus_mode: "sleeping" | "morning_plan" | "autonomy" | "self_programming" | "orchestrator";
  current_thought: string | null;
  active_goal_ids: string[];
  today_plan?: TodayPlan | null;
  last_action?: ToolExecutionResult | null;
  self_programming_job?: SelfProgrammingJob | null;
  orchestrator_session?: OrchestratorSession | null;
};

export type MacConsoleBootstrapStatus = {
  state:
    | "disabled"
    | "skipped_non_macos"
    | "script_missing"
    | "check_passed"
    | "check_error"
    | "autofix_succeeded"
    | "autofix_error"
    | "autofix_failed"
    | string;
  healthy: boolean;
  platform: string;
  enabled: boolean;
  attempted_autofix: boolean;
  summary: string;
  checked_at?: string | null;
  script_path?: string | null;
  check_exit_code?: number | null;
  apply_exit_code?: number | null;
};

export type ChatSubmissionResult = {
  response_id: string | null;
  assistant_message_id: string;
  reasoning_session_id?: string;
  reasoning_state?: ChatReasoningState;
};

export type ChatAttachment = {
  type: "folder" | "file" | "image";
  path: string;
  name?: string | null;
  mime_type?: string | null;
};

export type ChatReasoningRequest = {
  enabled: boolean;
  session_id?: string;
};

export type ChatReasoningState = {
  session_id: string;
  phase: "planning" | "exploring" | "finalizing" | "completed" | string;
  step_index: number;
  summary: string;
  updated_at: string;
};

export type ChatRequestBody = {
  message: string;
  attachments?: ChatAttachment[];
  mcp_servers?: string[];
  skills?: string[];
  reasoning?: ChatReasoningRequest;
};

export type FolderAccessLevel = "read_only" | "full_access";

export type ChatFolderPermission = {
  path: string;
  access_level: FolderAccessLevel;
};

export type ChatFolderPermissionsResponse = {
  permissions: ChatFolderPermission[];
};

export type ChatSkillEntry = {
  name: string;
  description?: string | null;
  path: string;
  trigger_prefixes: string[];
};

export type ChatSkillListResponse = {
  skills: ChatSkillEntry[];
};

export type ChatResumeRequest = {
  message: string;
  assistant_message_id: string;
  partial_content: string;
  reasoning_session_id?: string;
};

export type ChatHistoryMessage = {
  id?: string;
  role: "user" | "assistant";
  content: string;
  created_at?: string | null;
  session_id?: string | null;
  reasoning_session_id?: string | null;
  reasoning_state?: ChatReasoningState | null;
};

export type ChatHistoryResponse = {
  messages: ChatHistoryMessage[];
  limit?: number | null;
  offset?: number | null;
  has_more?: boolean | null;
  next_offset?: number | null;
};

export type ChatMessagesPageParams = {
  limit?: number;
  offset?: number;
};

export type Goal = {
  id: string;
  title: string;
  status: "active" | "paused" | "completed" | "abandoned";
  chain_id?: string | null;
  parent_goal_id?: string | null;
  generation?: number;
  source?: string | null;
  admission?: {
    score: number;
    recommended_decision: "admit" | "defer" | "drop";
    applied_decision: "admit" | "defer" | "drop";
    reason: string;
    deferred_retries?: number;
  } | null;
  created_at?: string | null;
  updated_at?: string | null;
};

export type TaskExecution = {
  goal_id: string;
  started_at: string;
  completed_at?: string | null;
  status: Goal["status"];
  progress: number;
  error?: string | null;
  metadata?: Record<string, unknown>;
};

export type TaskExecutionStats = {
  total_tasks: number;
  completed: number;
  failed: number;
  abandoned: number;
  active: number;
  success_rate: number;
};

export type GoalDecompositionResult = {
  parent_goal_id: string;
  subgoals: Goal[];
  complexity: {
    level: "简单" | "中等" | "复杂";
    score: number;
    factors: Record<string, unknown>;
  };
};

export type InnerWorldState = {
  time_of_day: "morning" | "afternoon" | "evening" | "night";
  energy: "low" | "medium" | "high";
  mood: "calm" | "engaged" | "tired";
  focus_tension: "low" | "medium" | "high";
  focus_stage?: "none" | "start" | "deepen" | "consolidate";
  focus_step?: number | null;
  latest_event?: string | null;
};

export type GoalsResponse = {
  goals: Goal[];
};

export type GoalAdmissionThresholds = {
  user_topic: { min_score: number; defer_score: number };
  world_event: { min_score: number; defer_score: number };
  chain_next: { min_score: number; defer_score: number };
};

export type GoalAdmissionStats = {
  mode: "off" | "shadow" | "enforce";
  today: {
    admit: number;
    defer: number;
    drop: number;
    wip_blocked: number;
  };
  admitted_stability_24h: {
    stable: number;
    re_deferred: number;
    dropped: number;
  };
  admitted_stability_24h_rate: number | null;
  admitted_stability_alert?: {
    level: "healthy" | "warning" | "danger" | "unknown";
    warning_rate: number;
    danger_rate: number;
  };
  deferred_queue_size: number;
  wip_limit: number;
  thresholds: GoalAdmissionThresholds;
};

export type GoalAdmissionCandidate = {
  source_type: "user_topic" | "world_event" | "chain_next";
  title: string;
  source_content?: string | null;
  chain_id?: string | null;
  parent_goal_id?: string | null;
  generation?: number;
  retry_count: number;
  fingerprint?: string | null;
};

export type DeferredGoalAdmissionCandidate = {
  candidate: GoalAdmissionCandidate;
  next_retry_at: string;
  last_reason: string;
};

export type RecentGoalAdmissionDecision = {
  candidate: GoalAdmissionCandidate;
  decision: "admit" | "defer" | "drop";
  reason: string;
  score: number;
  created_at: string;
  retry_at?: string | null;
  stability?: "stable" | "re_deferred" | "dropped";
};

export type GoalAdmissionCandidateSnapshot = {
  deferred: DeferredGoalAdmissionCandidate[];
  recent: RecentGoalAdmissionDecision[];
  admitted?: RecentGoalAdmissionDecision[];
};

const DEFAULT_BASE_URL = "http://127.0.0.1:8000";

function normalizeBaseUrl(value: string | undefined | null): string | null {
  if (!value) {
    return null;
  }
  const trimmed = value.trim();
  if (!trimmed) {
    return null;
  }
  return trimmed.replace(/\/+$/, "");
}

export function resolveApiBaseUrl(configuredBaseUrl: string | undefined | null = import.meta.env.VITE_API_BASE_URL): string {
  return normalizeBaseUrl(configuredBaseUrl) ?? DEFAULT_BASE_URL;
}

export const BASE_URL = resolveApiBaseUrl();

async function buildHttpError(response: Response): Promise<Error> {
  let detail = "";
  try {
    const contentType = response.headers.get("content-type") ?? "";
    if (contentType.includes("application/json")) {
      const payload = await response.json();
      if (typeof payload?.detail === "string") {
        detail = payload.detail;
      } else if (payload && typeof payload === "object") {
        detail = JSON.stringify(payload);
      }
    } else {
      const text = (await response.text()).trim();
      if (text) {
        detail = text;
      }
    }
  } catch {
    detail = "";
  }

  if (detail) {
    return new Error(`request failed: ${response.status} (${detail})`);
  }
  return new Error(`request failed: ${response.status}`);
}

export function isRequestStatusError(error: unknown, status: number): boolean {
  return error instanceof Error && error.message.startsWith(`request failed: ${status}`);
}

async function post<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: body ? JSON.stringify(body) : undefined,
  });

  if (!response.ok) {
    throw await buildHttpError(response);
  }

  return response.json();
}

async function put<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`, {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
    },
    body: body ? JSON.stringify(body) : undefined,
  });

  if (!response.ok) {
    throw await buildHttpError(response);
  }

  return response.json();
}

async function get<T>(path: string): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`);

  if (!response.ok) {
    throw await buildHttpError(response);
  }

  return response.json();
}

export function wake(): Promise<BeingState> {
  return post<BeingState>("/lifecycle/wake");
}

export function sleep(): Promise<BeingState> {
  return post<BeingState>("/lifecycle/sleep");
}

export function chat(messageOrBody: string | ChatRequestBody): Promise<ChatSubmissionResult> {
  if (typeof messageOrBody === "string") {
    return post<ChatSubmissionResult>("/chat", { message: messageOrBody });
  }
  return post<ChatSubmissionResult>("/chat", messageOrBody);
}

export function createOrchestratorSession(body: {
  goal: string;
  project_path: string;
}): Promise<OrchestratorSession> {
  return post<OrchestratorSession>("/orchestrator/sessions", body);
}

export function fetchOrchestratorSessions(filters?: OrchestratorSessionListFilters): Promise<OrchestratorSession[]> {
  const params = new URLSearchParams();
  for (const status of filters?.status ?? []) {
    params.append("status", status);
  }
  if (filters?.project?.trim()) {
    params.set("project", filters.project.trim());
  }
  if (filters?.from?.trim()) {
    params.set("from", filters.from.trim());
  }
  if (filters?.to?.trim()) {
    params.set("to", filters.to.trim());
  }
  if (filters?.keyword?.trim()) {
    params.set("keyword", filters.keyword.trim());
  }
  const query = params.toString();
  return get<OrchestratorSession[]>(query ? `/orchestrator/sessions?${query}` : "/orchestrator/sessions");
}

export function fetchOrchestratorScheduler(): Promise<OrchestratorSchedulerSnapshot> {
  return get<OrchestratorSchedulerSnapshot>("/orchestrator/scheduler");
}

export function tickOrchestratorScheduler(): Promise<OrchestratorSchedulerSnapshot> {
  return post<OrchestratorSchedulerSnapshot>("/orchestrator/scheduler/tick");
}

export function activateOrchestratorSession(sessionId: string): Promise<OrchestratorSession> {
  return post<OrchestratorSession>(`/orchestrator/sessions/${sessionId}/activate`);
}

export function generateOrchestratorPlan(sessionId: string): Promise<OrchestratorSession> {
  return post<OrchestratorSession>(`/orchestrator/sessions/${sessionId}/plan`);
}

export function approveOrchestratorPlan(sessionId: string): Promise<OrchestratorSession> {
  return post<OrchestratorSession>(`/orchestrator/sessions/${sessionId}/approve-plan`);
}

export function rejectOrchestratorPlan(
  sessionId: string,
  reason?: string,
): Promise<OrchestratorSession> {
  return post<OrchestratorSession>(
    `/orchestrator/sessions/${sessionId}/reject-plan`,
    reason ? { reason } : undefined,
  );
}

export function dispatchOrchestratorSession(sessionId: string): Promise<OrchestratorSession> {
  return post<OrchestratorSession>(`/orchestrator/sessions/${sessionId}/dispatch`);
}

export function fetchOrchestratorSession(sessionId: string): Promise<OrchestratorSession> {
  return get<OrchestratorSession>(`/orchestrator/sessions/${sessionId}`);
}

export function fetchOrchestratorTasks(sessionId: string): Promise<OrchestratorTask[]> {
  return get<OrchestratorTask[]>(`/orchestrator/sessions/${sessionId}/tasks`);
}

export function cancelOrchestratorSession(sessionId: string): Promise<OrchestratorSession> {
  return post<OrchestratorSession>(`/orchestrator/sessions/${sessionId}/cancel`);
}

export function resumeOrchestratorSession(sessionId: string): Promise<OrchestratorSession> {
  return post<OrchestratorSession>(`/orchestrator/sessions/${sessionId}/resume`);
}

export function submitOrchestratorDirective(
  sessionId: string,
  message: string,
): Promise<OrchestratorSession> {
  return post<OrchestratorSession>(`/orchestrator/sessions/${sessionId}/directive`, { message });
}

export async function fetchOrchestratorMessages(sessionId: string): Promise<OrchestratorMessage[]> {
  const payload = await get<OrchestratorMessage[] | { messages?: OrchestratorMessage[] }>(
    `/orchestrator/sessions/${sessionId}/messages`,
  );
  if (Array.isArray(payload)) {
    return payload;
  }
  return Array.isArray(payload.messages) ? payload.messages : [];
}

export function clearOrchestratorMessages(
  sessionId: string,
): Promise<OrchestratorMessagesDeleteResponse> {
  return del<OrchestratorMessagesDeleteResponse>(`/orchestrator/sessions/${sessionId}/messages`);
}

export function deleteOrchestratorSession(
  sessionId: string,
): Promise<OrchestratorSessionDeleteResponse> {
  return del<OrchestratorSessionDeleteResponse>(`/orchestrator/sessions/${sessionId}`);
}

export function chatWithOrchestrator(
  sessionId: string,
  message: string,
): Promise<OrchestratorChatSubmissionResult> {
  return post<OrchestratorChatSubmissionResult>(`/orchestrator/sessions/${sessionId}/chat`, { message });
}

export function runOrchestratorConsoleCommand(
  body: OrchestratorConsoleCommandRequest,
): Promise<OrchestratorConsoleCommandResponse> {
  return post<OrchestratorConsoleCommandResponse>("/orchestrator/console/command", body);
}

export function completeOrchestratorDelegate(body: {
  session_id: string;
  task_id: string;
  delegate_run_id: string;
  result: OrchestratorDelegateResult;
}): Promise<OrchestratorSession> {
  return post<OrchestratorSession>("/orchestrator/delegates/complete", body);
}

export function stopOrchestratorDelegate(
  body: OrchestratorDelegateStopRequest,
): Promise<OrchestratorSession> {
  return post<OrchestratorSession>("/orchestrator/delegates/stop", body);
}

export function fetchChatFolderPermissions(): Promise<ChatFolderPermissionsResponse> {
  return get<ChatFolderPermissionsResponse>("/chat/folder-permissions");
}

export function fetchChatSkills(): Promise<ChatSkillListResponse> {
  return get<ChatSkillListResponse>("/chat/skills");
}

export function upsertChatFolderPermission(
  path: string,
  accessLevel: FolderAccessLevel,
): Promise<ChatFolderPermissionsResponse> {
  return put<ChatFolderPermissionsResponse>("/chat/folder-permissions", {
    path,
    access_level: accessLevel,
  });
}

export async function removeChatFolderPermission(path: string): Promise<ChatFolderPermissionsResponse> {
  const response = await fetch(`${BASE_URL}/chat/folder-permissions?path=${encodeURIComponent(path)}`, {
    method: "DELETE",
  });
  if (!response.ok) {
    throw await buildHttpError(response);
  }
  return response.json();
}

export function resumeChat(body: ChatResumeRequest): Promise<ChatSubmissionResult> {
  return post<ChatSubmissionResult>("/chat/resume", body);
}

export function fetchState(): Promise<BeingState> {
  return get<BeingState>("/state");
}

export function fetchMacConsoleStatus(): Promise<MacConsoleBootstrapStatus> {
  return get<MacConsoleBootstrapStatus>("/environment/mac-console");
}

export function fetchMessages(params?: ChatMessagesPageParams): Promise<ChatHistoryResponse> {
  const query = new URLSearchParams();
  if (typeof params?.limit === "number") {
    query.set("limit", String(params.limit));
  }
  if (typeof params?.offset === "number") {
    query.set("offset", String(params.offset));
  }
  const suffix = query.toString();
  const path = suffix ? `/messages?${suffix}` : "/messages";
  return get<ChatHistoryResponse>(path);
}

export function fetchGoals(): Promise<GoalsResponse> {
  return get<GoalsResponse>("/goals");
}

export function fetchGoalAdmissionStats(): Promise<GoalAdmissionStats> {
  return get<GoalAdmissionStats>("/goals/admission/stats");
}

export function fetchGoalAdmissionCandidates(): Promise<GoalAdmissionCandidateSnapshot> {
  return get<GoalAdmissionCandidateSnapshot>("/goals/admission/candidates");
}

export function fetchWorld(): Promise<InnerWorldState> {
  return get<InnerWorldState>("/world");
}

export function updateGoalStatus(
  goalId: string,
  status: Goal["status"],
): Promise<Goal> {
  return post<Goal>(`/goals/${goalId}/status`, { status });
}

// 自我编程 API

/** 获取自我编程历史记录 */
export function fetchSelfProgrammingHistory(): Promise<{ entries: SelfProgrammingHistoryEntry[] }> {
  return get<{ entries: SelfProgrammingHistoryEntry[] }>("/self-programming/history");
}

/** 触发回滚操作 */
export function rollbackSelfProgrammingJob(jobId: string, reason?: string): Promise<{ success: boolean; message: string }> {
  return post<{ success: boolean; message: string }>(`/self-programming/${jobId}/rollback`, { reason });
}

/** 提交开工申请 */
export function requestStartSelfProgrammingJob(
  jobId: string,
  reason?: string,
): Promise<{ success: boolean; message: string; job_id: string }> {
  return post<{ success: boolean; message: string; job_id: string }>(
    `/self-programming/${jobId}/request-start`,
    reason ? { reason } : undefined,
  );
}

/** 确认开工 */
export function approveStartSelfProgrammingJob(
  jobId: string,
  reason?: string,
): Promise<{ success: boolean; message: string; job_id: string }> {
  return post<{ success: boolean; message: string; job_id: string }>(
    `/self-programming/${jobId}/approve-start`,
    reason ? { reason } : undefined,
  );
}

/** 拒绝开工 */
export function rejectStartSelfProgrammingJob(
  jobId: string,
  reason: string,
): Promise<{ success: boolean; message: string; job_id: string }> {
  return post<{ success: boolean; message: string; job_id: string }>(
    `/self-programming/${jobId}/reject-start`,
    { reason },
  );
}

/** 触发委托执行 */
export function delegateSelfProgrammingJob(
  jobId: string,
  provider = "codex",
): Promise<{ success: boolean; message: string; job_id: string }> {
  return post<{ success: boolean; message: string; job_id: string }>(
    `/self-programming/${jobId}/delegate`,
    { provider },
  );
}

/** 批准自我编程 Job */
export function approveSelfProgrammingJob(
  jobId: string,
  reason?: string,
): Promise<{ success: boolean; message: string; job_id: string }> {
  return post<{ success: boolean; message: string; job_id: string }>(
    `/self-programming/${jobId}/approve`,
    reason ? { reason } : undefined,
  );
}

/** 拒绝自我编程 Job */
export function rejectSelfProgrammingJob(
  jobId: string,
  reason: string,
): Promise<{ success: boolean; message: string; job_id: string }> {
  return post<{ success: boolean; message: string; job_id: string }>(
    `/self-programming/${jobId}/reject`,
    { reason },
  );
}

/** 获取自我编程冷却配置 */
export function fetchSelfProgrammingConfig(): Promise<SelfProgrammingRuntimeConfig> {
  return get<SelfProgrammingRuntimeConfig>("/config/self-programming");
}

/** 更新自我编程冷却配置 */
export function updateSelfProgrammingConfig(
  patch: Partial<SelfProgrammingRuntimeConfig>,
): Promise<SelfProgrammingRuntimeConfig> {
  return put<SelfProgrammingRuntimeConfig>("/config/self-programming", patch);
}

/** 获取目标准入稳定性阈值配置 */
export function fetchGoalAdmissionConfig(): Promise<GoalAdmissionRuntimeConfig> {
  return get<GoalAdmissionRuntimeConfig>("/config/goal-admission");
}

/** 更新目标准入稳定性阈值配置 */
export function updateGoalAdmissionConfig(
  patch: Partial<GoalAdmissionRuntimeConfig>,
): Promise<GoalAdmissionRuntimeConfig> {
  return put<GoalAdmissionRuntimeConfig>("/config/goal-admission", patch);
}

/** 获取目标准入阈值变更历史 */
export function fetchGoalAdmissionConfigHistory(
  limit = 10,
): Promise<GoalAdmissionConfigHistoryResponse> {
  return get<GoalAdmissionConfigHistoryResponse>(`/config/goal-admission/history?limit=${limit}`);
}

/** 回滚目标准入稳定性阈值到上一版 */
export function rollbackGoalAdmissionConfig(): Promise<GoalAdmissionConfigRollbackResponse> {
  return post<GoalAdmissionConfigRollbackResponse>("/config/goal-admission/rollback");
}

// ══════════════════════════════════════════════
// 人格 API
// ══════════════════════════════════════════════

export type EmotionType =
  | "joy" | "sadness" | "anger" | "fear" | "surprise"
  | "disgust" | "calm" | "engaged" | "proud" | "lonely"
  | "grateful" | "frustrated";

export type EmotionIntensity = "none" | "mild" | "moderate" | "strong" | "intense";

export type FormalLevel = "very_formal" | "formal" | "neutral" | "casual" | "slangy";

export type ExpressionHabit = "metaphor" | "direct" | "questioning" | "humorous" | "gentle";

export type SentenceStyleType = "short" | "mixed" | "long";

export type PersonaProfile = {
  name: string;
  identity: string;
  origin_story: string;
  features: {
    avatar_enabled: boolean;
  };
  personality: {
    openness: number;
    conscientiousness: number;
    extraversion: number;
    agreeableness: number;
    neuroticism: number;
  };
  speaking_style: {
    formal_level: FormalLevel;
    sentence_style: SentenceStyleType;
    expression_habit: ExpressionHabit;
    emoji_usage: string;
    verbal_tics: string[];
    response_length: string;
  };
  values: {
    core_values: { name: string; description: string; priority: number }[];
    boundaries: string[];
  };
  emotion: {
    primary_emotion: EmotionType;
    primary_intensity: EmotionIntensity;
    secondary_emotion: EmotionType | null;
    secondary_intensity: EmotionIntensity;
    mood_valence: number;
    arousal: number;
    is_calm: boolean;
    active_entry_count: number;
    active_entries: Array<{
      emotion_type: EmotionType;
      intensity: EmotionIntensity;
      reason: string;
      source: string;
    }>;
    last_updated: string | null;
  };
  version: number;
};

export type EmotionState = {
  primary_emotion: EmotionType;
  primary_intensity: EmotionIntensity;
  secondary_emotion: EmotionType | null;
  secondary_intensity: EmotionIntensity;
  mood_valence: number;
  arousal: number;
  is_calm: boolean;
  active_entry_count: number;
  active_entries: Array<{
    emotion_type: EmotionType;
    intensity: EmotionIntensity;
    reason: string;
    source: string;
  }>;
  last_updated: string | null;
};

/** 获取完整人格档案 */
export function fetchPersona(): Promise<PersonaProfile> {
  return get<PersonaProfile>("/persona");
}

/** 获取情绪状态 */
export function fetchEmotionState(): Promise<EmotionState> {
  return get<EmotionState>("/persona/emotion");
}

/** 更新人格基础信息 */
export function updatePersona(data: {
  name?: string;
  identity?: string;
  origin_story?: string;
}): Promise<{ success: boolean; profile: PersonaProfile }> {
  return put<{ success: boolean; profile: PersonaProfile }>("/persona", data);
}

/** 更新性格维度 */
export function updatePersonality(data: {
  openness?: number;
  conscientiousness?: number;
  extraversion?: number;
  agreeableness?: number;
  neuroticism?: number;
}): Promise<{ success: boolean; profile: PersonaProfile }> {
  return put<{ success: boolean; profile: PersonaProfile }>("/persona/personality", data);
}

/** 更新说话风格 */
export function updateSpeakingStyle(data: {
  formal_level?: FormalLevel;
  sentence_style?: SentenceStyleType;
  expression_habit?: ExpressionHabit;
  emoji_usage?: string;
  verbal_tics?: string[];
  response_length?: string;
}): Promise<{ success: boolean; profile: PersonaProfile }> {
  return put<{ success: boolean; profile: PersonaProfile }>("/persona/speaking-style", data);
}

/** 更新人格功能开关 */
export function updatePersonaFeatures(data: {
  avatar_enabled?: boolean;
}): Promise<{ success: boolean; profile: PersonaProfile }> {
  return put<{ success: boolean; profile: PersonaProfile }>("/persona/features", data);
}

/** 重置为默认人格 */
export function resetPersona(): Promise<{ success: boolean; profile: PersonaProfile }> {
  return post<{ success: boolean; profile: PersonaProfile }>("/persona/reset");
}

/** 初始化数字人：清空所有数据并重置为初始状态 */
export function initializePersona(): Promise<{
  success: boolean;
  message: string;
  cleared: { memories: number; goals: number };
  profile: PersonaProfile;
}> {
  return post<{
    success: boolean;
    message: string;
    cleared: { memories: number; goals: number };
    profile: PersonaProfile;
  }>("/persona/initialize");
}

// ══════════════════════════════════════════════
// 记忆 API
// ══════════════════════════════════════════════

export type MemoryKind = "fact" | "episodic" | "semantic" | "emotional" | "chat_raw";

export type MemoryStrength = "faint" | "weak" | "normal" | "vivid" | "core";

export type MemoryEmotion = "positive" | "negative" | "neutral" | "mixed";

export type MemoryEntryDisplay = {
  id: string;
  kind: MemoryKind;
  content: string;
  role: string | null;
  strength: MemoryStrength;
  importance: number;
  emotion_tag: MemoryEmotion;
  subject: string | null;
  keywords: string[];
  retention_score: number;
  access_count: number;
  created_at: string | null;
  last_accessed_at: string | null;
};

export type MemorySummary = {
  total_estimated: number;
  by_kind: Record<string, number>;
  recent_count: number;
  strong_memories: number;
  relationship: RelationshipSummary;
  available: boolean;
};

export type RelationshipSummary = {
  available: boolean;
  boundaries: string[];
  commitments: string[];
  preferences: string[];
};

export type MemorySearchResult = {
  entries: MemoryEntryDisplay[];
  total_count: number;
  query_summary: string | null;
};

export type KnowledgeReviewStatus = "pending_review" | "approved" | "rejected";

export type KnowledgeLifecycleStatus = "active" | "deleted" | "all";
export type KnowledgeSortBy = "created_at" | "reviewed_at";
export type KnowledgeSortOrder = "asc" | "desc";

export type KnowledgeItem = {
  id: string;
  kind: string;
  content: string;
  role: string | null;
  namespace: string | null;
  knowledge_type: string | null;
  knowledge_tags: string[];
  source_ref: string | null;
  version_tag: string | null;
  visibility: "internal" | "user";
  governance_source: "system" | "auto_extracted" | "manual";
  review_status: KnowledgeReviewStatus;
  reviewed_by: string | null;
  reviewed_at: string | null;
  review_note: string | null;
  status: "active" | "deleted";
  created_at: string | null;
  deleted_at: string | null;
};

export type KnowledgeItemsResponse = {
  items: KnowledgeItem[];
  total_count: number;
  sort_by?: KnowledgeSortBy;
  sort_order?: KnowledgeSortOrder;
  next_cursor?: string | null;
  next_offset?: number | null;
};

export type KnowledgeSummaryResponse = {
  total_count: number;
  active_count: number;
  deleted_count: number;
  by_review_status: Record<string, number>;
  by_kind: Record<string, number>;
};

export type KnowledgeBatchReviewResponse = {
  success: boolean;
  decision: "approve" | "reject" | "pend";
  updated: number;
  failed: number;
  updated_ids: string[];
  failed_ids: string[];
};

export type KnowledgeItemsQuery = {
  limit?: number;
  offset?: number;
  cursor?: string;
  sort_by?: KnowledgeSortBy;
  sort_order?: KnowledgeSortOrder;
  review_status?: KnowledgeReviewStatus;
  status?: KnowledgeLifecycleStatus;
  q?: string;
};

export type MemoryTimelineResponse = {
  entries: MemoryEntryDisplay[];
  total_count?: number;
  query_summary?: string | null;
};

export type MemoryTimelineQuery = {
  limit?: number;
  status?: "active" | "deleted" | "all";
  kind?: MemoryKind;
  namespace?: string;
  visibility?: "internal" | "user";
  q?: string;
};

/** 获取记忆系统统计摘要 */
export function fetchMemorySummary(): Promise<MemorySummary> {
  return get<MemorySummary>("/memory/summary");
}

/** 获取知识条目列表（专项治理） */
export function fetchKnowledgeItems(query?: KnowledgeItemsQuery): Promise<KnowledgeItemsResponse> {
  const params = new URLSearchParams();
  params.set("limit", String(query?.limit ?? 30));
  params.set("offset", String(query?.offset ?? 0));
  if (query?.cursor && query.cursor.trim().length > 0) {
    params.set("cursor", query.cursor.trim());
  }
  if (query?.sort_by) {
    params.set("sort_by", query.sort_by);
  }
  if (query?.sort_order) {
    params.set("sort_order", query.sort_order);
  }
  if (query?.review_status) {
    params.set("review_status", query.review_status);
  }
  if (query?.status) {
    params.set("status", query.status);
  }
  if (query?.q && query.q.trim().length > 0) {
    params.set("q", query.q.trim());
  }
  return get<KnowledgeItemsResponse>(`/knowledge/items?${params.toString()}`);
}

/** 获取知识治理汇总 */
export function fetchKnowledgeSummary(): Promise<KnowledgeSummaryResponse> {
  return get<KnowledgeSummaryResponse>("/knowledge/summary");
}

/** 人工创建知识条目 */
export function createKnowledgeItem(data: {
  kind: MemoryKind;
  content: string;
  role?: string | null;
  knowledge_type?: string | null;
  knowledge_tags?: string[];
  source_ref?: string | null;
  version_tag?: string | null;
  visibility?: "internal" | "user";
  reviewer?: string | null;
  review_note?: string | null;
}): Promise<{ success: boolean; item: KnowledgeItem }> {
  return post<{ success: boolean; item: KnowledgeItem }>("/knowledge/items", data);
}

/** 审核知识条目 */
export function reviewKnowledgeItem(
  knowledgeId: string,
  data: {
    decision: "approve" | "reject" | "pend";
    reviewer?: string | null;
    review_note?: string | null;
  },
): Promise<{ success: boolean; item: KnowledgeItem }> {
  return post<{ success: boolean; item: KnowledgeItem }>(
    `/knowledge/items/${encodeURIComponent(knowledgeId)}/review`,
    data,
  );
}

/** 批量审核知识条目 */
export function reviewKnowledgeItemsBatch(data: {
  knowledge_ids: string[];
  decision: "approve" | "reject" | "pend";
  reviewer?: string | null;
  review_note?: string | null;
}): Promise<KnowledgeBatchReviewResponse> {
  return post<KnowledgeBatchReviewResponse>("/knowledge/items/review-batch", data);
}

/** 获取记忆时间线 */
export function fetchMemoryTimeline(
  limitOrQuery?: number | MemoryTimelineQuery,
): Promise<MemoryTimelineResponse> {
  const query: MemoryTimelineQuery =
    typeof limitOrQuery === "number" ? { limit: limitOrQuery } : (limitOrQuery ?? {});
  const params = new URLSearchParams();
  params.set("limit", String(query.limit ?? 30));
  if (query.status) {
    params.set("status", query.status);
  }
  if (query.kind) {
    params.set("kind", query.kind);
  }
  if (query.namespace) {
    params.set("namespace", query.namespace);
  }
  if (query.visibility) {
    params.set("visibility", query.visibility);
  }
  if (query.q && query.q.trim().length > 0) {
    params.set("q", query.q.trim());
  }
  return get<MemoryTimelineResponse>(`/memory/timeline?${params.toString()}`);
}

/** 搜索记忆 */
export function searchMemories(query: string, limit?: number): Promise<MemorySearchResult> {
  return get<MemorySearchResult>(`/memory/search?q=${encodeURIComponent(query)}&limit=${limit ?? 10}`);
}

/** 手动创建记忆 */
export function createMemory(data: {
  kind: MemoryKind;
  content: string;
  role?: string | null;
  strength?: MemoryStrength;
  importance?: number;
  emotion_tag?: MemoryEmotion;
  keywords?: string[] | null;
  subject?: string | null;
}): Promise<{ success: boolean; entry: MemoryEntryDisplay }> {
  return post<{ success: boolean; entry: MemoryEntryDisplay }>("/memory", data);
}

// ══════════════════════════════════════════════
// 记忆操作 API（删除 / 更新 / 标星）
// ══════════════════════════════════════════════

/** 删除指定记忆 */
export function deleteMemory(memoryId: string): Promise<{ success: boolean; deleted_id: string }> {
  return fetch(`${BASE_URL}/memory/${encodeURIComponent(memoryId)}`, { method: "DELETE" }).then((r) => {
    if (!r.ok) throw new Error(`delete memory failed: ${r.status}`);
    return r.json();
  });
}

/** 批量删除记忆 */
export function batchDeleteMemories(memoryIds: string[]): Promise<{ success: boolean; deleted: number; failed: number; total: number }> {
  return post<{ success: boolean; deleted: number; failed: number; total: number }>("/memory/batch-delete", { memory_ids: memoryIds });
}

/** 更新记忆内容或属性 */
export function updateMemory(
  memoryId: string,
  data: {
    content?: string;
    kind?: MemoryKind;
    importance?: number;
    strength?: MemoryStrength;
    emotion_tag?: MemoryEmotion;
    keywords?: string[] | null;
    subject?: string | null;
  },
): Promise<{ success: boolean; entry: MemoryEntryDisplay | null }> {
  return put<{ success: boolean; entry: MemoryEntryDisplay | null }>(
    `/memory/${encodeURIComponent(memoryId)}`,
    data,
  );
}

/** 标记/取消标记记忆为重要 */
export function starMemory(
  memoryId: string,
  important: boolean = true,
): Promise<{ success: boolean; starred: boolean; memory_id: string }> {
  return post<{ success: boolean; starred: boolean; memory_id: string }>(
    `/memory/${encodeURIComponent(memoryId)}/star`,
    { important },
  );
}

/** HTTP DELETE/PUT 辅助函数 */
async function del<T>(path: string): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`, { method: "DELETE" });
  if (!response.ok) {
    throw await buildHttpError(response);
  }
  return response.json();
}

// ══════════════════════════════════════════════
// 工具 API
// ══════════════════════════════════════════════

export type ToolSafetyLevel = "safe" | "restricted" | "dangerous" | "blocked";

export type ToolInfo = {
  name: string;
  description: string;
  safety_level: ToolSafetyLevel;
  examples: string[];
};

export type ToolsListResponse = {
  total_count: number;
  by_category: Record<string, ToolInfo[]>;
  safety_levels: string[];
};

export type ToolExecutionResult = {
  command: string;
  output: string;
  stderr?: string;
  exit_code?: number;
  success?: boolean;
  timed_out?: boolean;
  truncated?: boolean;
  duration_seconds?: number;
  executed_at?: string;
  tool_name?: string | null;
  safety_level?: ToolSafetyLevel | null;
  working_directory?: string;
  error?: string;
};

export type ToolHistoryEntry = {
  id: string;
  command: string;
  output: string;
  exit_code: number;
  success: boolean;
  timed_out: boolean;
  duration_seconds: number;
  tool_name: string | null;
  safety_level: string | null;
  created_at: string;
  error?: string;
};

export type ToolsHistoryResponse = {
  entries: ToolHistoryEntry[];
  total: number;
};

export type ToolsStatusResponse = {
  sandbox_enabled: boolean;
  allowed_command_count: number;
  safety_filter: string;
  working_directory: string;
  timeout_seconds: number;
  statistics: {
    total_executions: number;
    success_count: number;
    failed_count: number;
    timeout_count: number;
    success_rate: number;
  };
  recently_used_tools: [string, number][];
  history_size: number;
};

// ── 文件操作类型 ────────────────────────────────────

export type FileReadResult = {
  path: string;
  content: string;
  size_bytes: number;
  encoding: string;
  line_count: number;
  truncated: boolean;
  mime_type?: string;
  error?: string;
};

export type DirectoryEntry = {
  name: string;
  path: string;
  type: "file" | "dir" | "symlink" | "other";
  size_bytes: number;
  modified_at: string | null;
};

export type DirectoryListResult = {
  path: string;
  entries: DirectoryEntry[];
  total_files: number;
  total_dirs: number;
  truncated: boolean;
  error?: string;
};

export type SearchResult = {
  query: string;
  matches: Array<{
    file: string;
    line: number;
    context: string;
  }>;
  total_matches: number;
  search_duration_seconds: number;
  error?: string;
};

// ── API 函数 ──────────────────────────────────────────

/** 列出可用工具 */
export function fetchTools(): Promise<ToolsListResponse> {
  return get<ToolsListResponse>("/tools");
}

/** 执行工具命令 */
export function executeTool(command: string, timeoutOverride?: number): Promise<ToolExecutionResult> {
  return post<ToolExecutionResult>("/tools/execute", {
    command,
    timeout_override: timeoutOverride,
  });
}

/** 获取执行历史 */
export function fetchToolHistory(limit?: number): Promise<ToolsHistoryResponse> {
  return get<ToolsHistoryResponse>(`/tools/history?limit=${limit ?? 30}`);
}

/** 清空执行历史 */
export function clearToolHistory(): Promise<{ cleared: number; message: string }> {
  return fetch("/tools/history", { method: "DELETE" }).then((r) => r.json());
}

/** 获取工具系统状态 */
export function fetchToolsStatus(): Promise<ToolsStatusResponse> {
  return get<ToolsStatusResponse>("/tools/status");
}

// ── 文件操作 API ──────────────────────────────────────

/** 读取文件 */
export function readFile(path: string, maxBytes?: number): Promise<FileReadResult> {
  const params = `?path=${encodeURIComponent(path)}&max_bytes=${maxBytes ?? 512 * 1024}`;
  return get<FileReadResult>(`/tools/files/read${params}`);
}

/** 列出目录 */
export function listDirectory(path?: string, recursive?: boolean, pattern?: string | null): Promise<DirectoryListResult> {
  const params = new URLSearchParams();
  if (path) params.set("path", path);
  if (recursive) params.set("recursive", "true");
  if (pattern) params.set("pattern", pattern);
  return get<DirectoryListResult>(`/tools/files/list?${params.toString()}`);
}

/** 搜索文件内容 */
export function searchFiles(
  query: string,
  searchPath?: string,
  filePattern?: string,
  maxResults?: number,
): Promise<SearchResult> {
  const params = new URLSearchParams({
    query,
    search_path: searchPath || ".",
    file_pattern: filePattern || "*.py",
    max_results: String(maxResults || 20),
  });
  return get<SearchResult>(`/tools/files/search?${params.toString()}`);
}

// ══════════════════════════════════════════════
// 任务管理增强 API
// ══════════════════════════════════════════════

/** 分解目标为子任务 */
export function decomposeGoal(goalId: string, maxSubtasks?: number): Promise<GoalDecompositionResult> {
  return get<GoalDecompositionResult>(`/goals/${goalId}/decompose?max_subtasks=${maxSubtasks ?? 5}`);
}

/** 获取任务执行统计 */
export function fetchTaskExecutionStats(): Promise<TaskExecutionStats> {
  return get<TaskExecutionStats>("/goals/execution/stats");
}

/** 获取活跃任务执行记录 */
export function fetchActiveTaskExecutions(): Promise<TaskExecution[]> {
  return get<TaskExecution[]>("/goals/execution/active");
}

/** 更新任务进度 */
export function updateTaskProgress(goalId: string, progress: number): Promise<{ success: boolean }> {
  return post<{ success: boolean }>(`/goals/${goalId}/progress`, { progress });
}

/** 获取任务调度状态 */
export function fetchSchedulerStatus(): Promise<{
  max_concurrent: number;
  current_running: number;
  available_slots: number;
  running_task_ids: string[];
}> {
  return get<{
    max_concurrent: number;
    current_running: number;
    available_slots: number;
    running_task_ids: string[];
  }>("/goals/scheduler/status");
}

// ══════════════════════════════════════════════
// 配置 API
// ══════════════════════════════════════════════

export type AppConfig = {
  chat_context_limit: number;
  chat_provider: string;
  chat_model: string;
  chat_read_timeout_seconds: number;
  chat_continuous_reasoning_enabled: boolean;
  chat_mcp_enabled: boolean;
  chat_mcp_servers: ChatMcpServerConfig[];
};

export type ChatMcpServerConfig = {
  server_id: string;
  command: string;
  args: string[];
  cwd?: string | null;
  env: Record<string, string>;
  enabled: boolean;
  timeout_seconds: number;
};

export type DataEnvironmentStatus = {
  testing_mode: boolean;
  mempalace_palace_path: string;
  mempalace_wing: string;
  mempalace_room: string;
  default_backup_directory: string;
  switch_backup_path?: string | null;
};

export type DataEnvironmentUpdatePayload = {
  testing_mode: boolean;
  backup_before_switch?: boolean;
};

export type DataBackupCreatePayload = {
  backup_path?: string | null;
};

export type DataBackupCreateResponse = {
  backup_path: string;
  created_at: string;
  included_keys: string[];
};

export type DataBackupImportPayload = {
  backup_path: string;
  make_pre_import_backup?: boolean;
};

export type DataBackupImportResponse = {
  imported_from: string;
  restored_keys: string[];
  pre_import_backup_path?: string | null;
};

export type ChatModelProviderItem = {
  provider_id: string;
  provider_name: string;
  models: string[];
  default_model: string;
  error?: string | null;
};

export type ChatModelsResponse = {
  providers: ChatModelProviderItem[];
  current_provider: string;
  current_model: string;
};

export const DEFAULT_CHAT_PROVIDER = "openai";
export const DEFAULT_CHAT_MODEL = "gpt-5.4";

function normalizeAppConfig(payload: Partial<AppConfig> | null | undefined): AppConfig {
  const source = payload ?? {};
  const rawMcpServers = Array.isArray(source.chat_mcp_servers) ? source.chat_mcp_servers : [];
  const normalizedMcpServers: ChatMcpServerConfig[] = rawMcpServers
    .map((item) => {
      if (!item || typeof item !== "object") return null;
      const candidate = item as Partial<ChatMcpServerConfig>;
      if (typeof candidate.server_id !== "string" || !candidate.server_id.trim()) return null;
      if (typeof candidate.command !== "string" || !candidate.command.trim()) return null;
      return {
        server_id: candidate.server_id.trim(),
        command: candidate.command.trim(),
        args: Array.isArray(candidate.args) ? candidate.args.filter((arg): arg is string => typeof arg === "string") : [],
        cwd: typeof candidate.cwd === "string" ? candidate.cwd : null,
        env:
          candidate.env && typeof candidate.env === "object"
            ? Object.fromEntries(
                Object.entries(candidate.env).filter(
                  (entry): entry is [string, string] => typeof entry[0] === "string" && typeof entry[1] === "string",
                ),
              )
            : {},
        enabled: typeof candidate.enabled === "boolean" ? candidate.enabled : true,
        timeout_seconds:
          typeof candidate.timeout_seconds === "number" && Number.isFinite(candidate.timeout_seconds)
            ? Math.max(1, Math.min(120, Math.floor(candidate.timeout_seconds)))
            : 20,
      };
    })
    .filter((item): item is ChatMcpServerConfig => item !== null);

  return {
    chat_context_limit: typeof source.chat_context_limit === "number" ? source.chat_context_limit : 6,
    chat_provider:
      typeof source.chat_provider === "string" && source.chat_provider.trim()
        ? source.chat_provider.trim()
        : DEFAULT_CHAT_PROVIDER,
    chat_model:
      typeof source.chat_model === "string" && source.chat_model.trim() ? source.chat_model.trim() : DEFAULT_CHAT_MODEL,
    chat_read_timeout_seconds:
      typeof source.chat_read_timeout_seconds === "number" ? source.chat_read_timeout_seconds : 180,
    chat_continuous_reasoning_enabled:
      typeof source.chat_continuous_reasoning_enabled === "boolean" ? source.chat_continuous_reasoning_enabled : false,
    chat_mcp_enabled: typeof source.chat_mcp_enabled === "boolean" ? source.chat_mcp_enabled : false,
    chat_mcp_servers: normalizedMcpServers,
  };
}

/** 获取配置 */
export async function fetchConfig(): Promise<AppConfig> {
  const payload = await get<Partial<AppConfig>>("/config");
  return normalizeAppConfig(payload);
}

/** 更新配置 */
export async function updateConfig(data: Partial<AppConfig>): Promise<AppConfig> {
  const payload = await put<Partial<AppConfig>>("/config", data);
  return normalizeAppConfig(payload);
}

/** 获取可选聊天模型列表 */
export function fetchChatModels(): Promise<ChatModelsResponse> {
  return get<ChatModelsResponse>("/config/chat-models");
}

export function fetchDataEnvironmentStatus(): Promise<DataEnvironmentStatus> {
  return get<DataEnvironmentStatus>("/config/data-environment");
}

export function updateDataEnvironmentStatus(
  payload: DataEnvironmentUpdatePayload,
): Promise<DataEnvironmentStatus> {
  return put<DataEnvironmentStatus>("/config/data-environment", payload);
}

export function createDataBackup(
  payload: DataBackupCreatePayload = {},
): Promise<DataBackupCreateResponse> {
  return post<DataBackupCreateResponse>("/config/data-backup", payload);
}

export function importDataBackup(
  payload: DataBackupImportPayload,
): Promise<DataBackupImportResponse> {
  return post<DataBackupImportResponse>("/config/data-backup/import", payload);
}
