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
  target_area: string;
  status:
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
};

// 自我编程历史记录
export type SelfProgrammingHistoryEntry = {
  job_id: string;
  target_area: string;
  reason: string;
  status: string;
  outcome: string;
  touched_files: string[];
  created_at: string;
  completed_at?: string | null;
  health_score?: number | null;
  had_rollback?: boolean;
};

export type BeingState = {
  mode: "awake" | "sleeping";
  focus_mode: "sleeping" | "morning_plan" | "autonomy" | "self_programming";
  current_thought: string | null;
  active_goal_ids: string[];
  today_plan?: TodayPlan | null;
  last_action?: ToolExecutionResult | null;
  self_programming_job?: SelfProgrammingJob | null;
};

export type ChatSubmissionResult = {
  response_id: string | null;
  assistant_message_id: string;
};

export type ChatResumeRequest = {
  message: string;
  assistant_message_id: string;
  partial_content: string;
};

export type ChatHistoryMessage = {
  role: "user" | "assistant";
  content: string;
};

export type ChatHistoryResponse = {
  messages: ChatHistoryMessage[];
};

export type Goal = {
  id: string;
  title: string;
  status: "active" | "paused" | "completed" | "abandoned";
  chain_id?: string | null;
  parent_goal_id?: string | null;
  generation?: number;
  source?: string | null;
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

export type AutobioResponse = {
  entries: string[];
};

export const BASE_URL = "http://127.0.0.1:8000";

async function post<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: body ? JSON.stringify(body) : undefined,
  });

  if (!response.ok) {
    throw new Error(`request failed: ${response.status}`);
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
    throw new Error(`request failed: ${response.status}`);
  }

  return response.json();
}

async function get<T>(path: string): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`);

  if (!response.ok) {
    throw new Error(`request failed: ${response.status}`);
  }

  return response.json();
}

export function wake(): Promise<BeingState> {
  return post<BeingState>("/lifecycle/wake");
}

export function sleep(): Promise<BeingState> {
  return post<BeingState>("/lifecycle/sleep");
}

export function chat(message: string): Promise<ChatSubmissionResult> {
  return post<ChatSubmissionResult>("/chat", { message });
}

export function resumeChat(body: ChatResumeRequest): Promise<ChatSubmissionResult> {
  return post<ChatSubmissionResult>("/chat/resume", body);
}

export function fetchState(): Promise<BeingState> {
  return get<BeingState>("/state");
}

export function fetchMessages(): Promise<ChatHistoryResponse> {
  return get<ChatHistoryResponse>("/messages");
}

export function fetchGoals(): Promise<GoalsResponse> {
  return get<GoalsResponse>("/goals");
}

export function fetchWorld(): Promise<InnerWorldState> {
  return get<InnerWorldState>("/world");
}

export function fetchAutobio(): Promise<AutobioResponse> {
  return get<AutobioResponse>("/autobio");
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

/** 重置为默认人格 */
export function resetPersona(): Promise<{ success: boolean; profile: PersonaProfile }> {
  return post<{ success: boolean; profile: PersonaProfile }>("/persona/reset");
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
  available: boolean;
};

export type MemorySearchResult = {
  entries: MemoryEntryDisplay[];
  total_count: number;
  query_summary: string | null;
};

export type MemoryTimelineResponse = {
  entries: MemoryEntryDisplay[];
};

/** 获取记忆系统统计摘要 */
export function fetchMemorySummary(): Promise<MemorySummary> {
  return get<MemorySummary>("/memory/summary");
}

/** 获取记忆时间线 */
export function fetchMemoryTimeline(limit?: number): Promise<MemoryTimelineResponse> {
  return get<MemoryTimelineResponse>(`/memory/timeline?limit=${limit ?? 30}`);
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
  return post<{ success: boolean; entry: MemoryEntryDisplay | null }>(
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
  if (!response.ok) throw new Error(`request failed: ${response.status}`);
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
};

/** 获取配置 */
export function fetchConfig(): Promise<AppConfig> {
  return get<AppConfig>("/config");
}

/** 更新配置 */
export function updateConfig(data: Partial<AppConfig>): Promise<AppConfig> {
  return put<AppConfig>("/config", data);
}
