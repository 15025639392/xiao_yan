export * from "./apiClient";
export * from "./apiConfig";
export * from "./apiMemory";
export * from "./apiPersona";
export * from "./apiXiaohongshu";

import { BASE_URL, buildHttpError, get, post, put } from "./apiClient";

export type BrowserOrganUpdate = {
  binding_status?: string;
  health_status?: string;
  driver_name?: string;
  driver_version?: string;
  browser_binary_ready?: boolean;
  requires_approval_for_bind?: boolean;
  last_error?: string;
};

export type BrowserSessionUpdate = {
  session_id?: string;
  status?: string;
  current_url?: string;
  page_title?: string;
  opened_at?: string;
  interaction_level?: string;
  last_snapshot_summary?: string;
  last_error?: string;
};

export async function updateBrowserOrgan(update: BrowserOrganUpdate): Promise<{ ok: boolean }> {
  return post<{ ok: boolean }>("/browser/organ", update);
}

export async function updateBrowserSession(update: BrowserSessionUpdate): Promise<{ ok: boolean }> {
  return post<{ ok: boolean }>("/browser/session", update);
}

export type XhsWorkDomainProfile = {
  work_type: string;
  account_name: string;
  account_positioning: string;
  target_audience: string;
  expression_style: string;
  scouting_interval_hours: number;
  auto_publish_selector: string;
};

export type XhsWorkDomainState = {
  status: string;
  current_focus: string;
  backlog_count: number;
  active_task_ids: string[];
  last_published_at: string | null;
  last_scouting_at: string | null;
  current_bottleneck: string;
  next_recommended_action: string;
  pending_drafts: Array<{
    draft_id: string;
    title: string;
    body: string;
    generated_at: string;
    status: string;
  }>;
  published_history: Array<{
    draft_id: string;
    title: string;
    published_at: string;
    post_url: string;
  }>;
};

export type XhsWorkDomainGoals = {
  north_star: string;
  weekly_goals: string[];
  monthly_content_target: number;
};

export type XhsWorkDomainResponse = {
  available: boolean;
  profile?: XhsWorkDomainProfile;
  state?: XhsWorkDomainState;
  goals?: XhsWorkDomainGoals;
};

export type XhsWorkDomainUpdate = {
  status?: string;
  current_focus?: string;
  backlog_count?: number;
  active_task_ids?: string[];
  last_published_at?: string;
  current_bottleneck?: string;
  next_recommended_action?: string;
  account_name?: string;
  account_positioning?: string;
  target_audience?: string;
  expression_style?: string;
  scouting_interval_hours?: number;
  auto_publish_selector?: string;
  north_star?: string;
  weekly_goals?: string[];
  monthly_content_target?: number;
};

export async function fetchXhsWorkDomain(): Promise<XhsWorkDomainResponse> {
  return get<XhsWorkDomainResponse>("/xhs-work-domain");
}

export async function updateXhsWorkDomain(update: XhsWorkDomainUpdate): Promise<{ ok: boolean }> {
  return patch<{ ok: boolean }>("/xhs-work-domain", update);
}

export type FocusContext = {
  goal_title: string;
  source_kind: string;
  source_label: string;
  reason_kind: string;
  reason_label: string;
  prompt_summary: string;
};

export type FocusEffort = {
  goal_id?: string | null;
  goal_title: string;
  why_now: string;
  action_kind: string;
  did_what: string;
  effect?: string | null;
  next_hint?: string | null;
  created_at: string;
};

export type FocusSubject = {
  kind: string;
  title: string;
  why_now: string;
  source_ref?: string | null;
  goal_id?: string | null;
};

export type BrowserOrganState = {
  binding_status: "bound" | "unbound" | "pending";
  health_status: "healthy" | "degraded" | "unavailable";
  knowledge_status: string;
  last_checked_at: string;
  driver_name?: string;
  driver_version?: string;
  browser_binary_ready: boolean;
  last_error?: string;
};

export type BrowserSessionState = {
  session_id: string;
  status: "active" | "closed" | "error";
  current_url?: string;
  page_title?: string;
};

export type BeingState = {
  mode: "awake" | "sleeping";
  focus_mode: "sleeping" | "autonomy";
  current_thought: string | null;
  last_action?: ToolExecutionResult | null;
  focus_subject?: FocusSubject | null;
  focus_context?: FocusContext | null;
  focus_effort?: FocusEffort | null;
  browser_organ?: BrowserOrganState | null;
  browser_session?: BrowserSessionState | null;
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
  request_key?: string;
  user_timezone?: string;
  user_local_time?: string;
  user_time_of_day?: "morning" | "afternoon" | "evening" | "night";
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
  request_key?: string;
  reasoning_session_id?: string;
  user_timezone?: string;
  user_local_time?: string;
  user_time_of_day?: "morning" | "afternoon" | "evening" | "night";
};

export type ChatHistoryMessage = {
  id?: string;
  role: "user" | "assistant";
  content: string;
  created_at?: string | null;
  session_id?: string | null;
  request_key?: string | null;
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

export type InnerWorldState = {
  time_of_day: "morning" | "afternoon" | "evening" | "night";
  energy: "low" | "medium" | "high";
  mood: "calm" | "engaged" | "tired";
  focus_tension: "low" | "medium" | "high";
  focus_stage?: "none" | "start" | "deepen" | "consolidate";
  focus_step?: number | null;
  latest_event?: string | null;
};

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

export type AutobioResponse = {
  entries: string[];
};

export function fetchAutobio(): Promise<AutobioResponse> {
  return get<AutobioResponse>("/runtime/autobio");
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

export function fetchWorld(): Promise<InnerWorldState> {
  return get<InnerWorldState>("/world");
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
