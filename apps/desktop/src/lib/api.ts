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

export type ActionResult = {
  command: string;
  output: string;
};

export type EditKind = "replace" | "create" | "insert";

export type SelfImprovementEdit = {
  file_path: string;
  search_text?: string;
  replace_text?: string;
  kind: EditKind;
  insert_after?: string | null;
  file_content?: string | null;
};

export type SelfImprovementVerification = {
  commands: string[];
  passed: boolean;
  summary?: string | null;
};

export type SelfImprovementJob = {
  id: string;
  reason: string;
  target_area: string;
  status:
    | "pending"
    | "diagnosing"
    | "patching"
    | "pending_approval"   // Phase 6
    | "verifying"
    | "applied"
    | "failed"
    | "rejected";          // Phase 6
  spec: string;
  patch_summary?: string | null;
  red_verification?: SelfImprovementVerification | null;
  verification?: SelfImprovementVerification | null;
  edits?: SelfImprovementEdit[];          // Phase 1+: 最终应用的编辑列表
  test_edits?: SelfImprovementEdit[];     // Phase 2: 多候选方案的测试编辑
  touched_files?: string[];
  cooldown_until?: string | null;

  // ── Phase 3: Git 工作流 ──
  branch_name?: string | null;           // 本次自编程使用的分支名
  commit_hash?: string | null;           // commit 完整 hash
  commit_message?: string | null;        // commit message 文本
  candidate_label?: string | null;       // 多候选模式下选中的方案标签

  // ── Phase 4: 沙箱 + 冲突检测 ──
  sandbox_prechecked?: boolean;          // 是否经过沙箱预验证
  sandbox_result?: string | null;        // 预验结果摘要
  conflict_severity?: string;            // safe / warning / blocking
  conflict_details?: string | null;      // 冲突详情

  // ── Phase 5: 回滚恢复 + 健康度 ──
  health_score?: number | null;          // 健康检查总分 (0~100)
  health_grade?: string | null;          // excellent/good/fair/poor/critical
  rollback_info?: string | null;         // 回滚信息
  snapshot_taken?: boolean;              // 是否在 apply 前创建了差异快照

  // ── Phase 6: 审批字段 ──
  approval_requested_at?: string | null; // 发起审批时间 (ISO)
  approval_edits_summary?: string | null;// 编辑摘要（供审批查看）
  approval_reason?: string | null;       // 拒绝原因
};

// ── 健康度报告（Phase 5）──
export type HealthDimensionScore = {
  name: string;
  score: number;
  weight: number;
  weighted_score: number;
  details: string;
};

export type HealthReport = {
  overall_score: number;
  grade: string;
  trend: "improving" | "stable" | "declining" | "unknown";
  dimensions: HealthDimensionScore[];
  summary: string;
  rollback_suggested: boolean;
  assessed_at: string;
};

// ── 自编程历史记录（Phase 4+）──
export type SelfImprovementHistoryEntry = {
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
  focus_mode: "sleeping" | "morning_plan" | "autonomy" | "self_improvement";
  current_thought: string | null;
  active_goal_ids: string[];
  today_plan?: TodayPlan | null;
  last_action?: ActionResult | null;
  self_improvement_job?: SelfImprovementJob | null;
};

export type ChatResult = {
  response_id: string | null;
  output_text: string;
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

const BASE_URL = "http://127.0.0.1:8000";

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

export function chat(message: string): Promise<ChatResult> {
  return post<ChatResult>("/chat", { message });
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

// ── 自编程系统 API（Phase 1-5）──

/** 获取自编程历史记录 */
export function fetchSelfImprovementHistory(): Promise<{ entries: SelfImprovementHistoryEntry[] }> {
  return get<{ entries: SelfImprovementHistoryEntry[] }>("/self-improvement/history");
}

/** 触发回滚操作 */
export function rollbackSelfImprovementJob(jobId: string, reason?: string): Promise<{ success: boolean; message: string }> {
  return post<{ success: boolean; message: string }>(`/self-improvement/${jobId}/rollback`, { reason });
}

/** 获取健康度报告 */
export function fetchHealthReport(): Promise<HealthReport> {
  return get<HealthReport>("/self-improvement/health");
}

// ── 审批交互 API（Phase 6）──

export type PendingApprovalResponse = {
  pending: SelfImprovementJob | null;
  has_pending: boolean;
};

/** 获取当前等待审批的 Job */
export function fetchPendingApproval(): Promise<PendingApprovalResponse> {
  return get<PendingApprovalResponse>("/self-improvement/pending");
}

/** 批准自编程 Job */
export function approveSelfImprovementJob(
  jobId: string,
  reason?: string,
): Promise<{ success: boolean; message: string; job_id: string }> {
  return post<{ success: boolean; message: string; job_id: string }>(
    `/self-improvement/${jobId}/approve`,
    reason ? { reason } : undefined,
  );
}

/** 拒绝自编程 Job */
export function rejectSelfImprovementJob(
  jobId: string,
  reason: string,
): Promise<{ success: boolean; message: string; job_id: string }> {
  return post<{ success: boolean; message: string; job_id: string }>(
    `/self-improvement/${jobId}/reject`,
    { reason },
  );
}
