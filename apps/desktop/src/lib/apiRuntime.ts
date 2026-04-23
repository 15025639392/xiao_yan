import { get, patch, post } from "./apiClient";
import type { ToolExecutionResult } from "./apiTools";

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

export type XhsWorkDomainProfile = {
  work_type: string;
  account_name: string;
  account_positioning: string;
  target_audience: string;
  expression_style: string;
  scouting_interval_hours: number;
  publish_mode: "manual" | "auto";
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
  review_session_id: string;
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
  publish_mode?: "manual" | "auto";
  north_star?: string;
  weekly_goals?: string[];
  monthly_content_target?: number;
  pending_drafts?: Array<{
    draft_id: string;
    title: string;
    body: string;
    generated_at: string;
    status: string;
  }>;
};

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

export type InnerWorldState = {
  time_of_day: "morning" | "afternoon" | "evening" | "night";
  energy: "low" | "medium" | "high";
  mood: "calm" | "engaged" | "tired";
  focus_tension: "low" | "medium" | "high";
  focus_stage?: "none" | "start" | "deepen" | "consolidate";
  focus_step?: number | null;
  latest_event?: string | null;
};

export type AutobioResponse = {
  entries: string[];
};

export async function updateBrowserOrgan(update: BrowserOrganUpdate): Promise<{ ok: boolean }> {
  return post<{ ok: boolean }>("/browser/organ", update);
}

export async function updateBrowserSession(update: BrowserSessionUpdate): Promise<{ ok: boolean }> {
  return post<{ ok: boolean }>("/browser/session", update);
}

export async function wakeLifecycle(): Promise<BeingState> {
  return post<BeingState>("/lifecycle/wake", {});
}

export async function sleepLifecycle(): Promise<BeingState> {
  return post<BeingState>("/lifecycle/sleep", {});
}

export async function fetchXhsWorkDomain(): Promise<XhsWorkDomainResponse> {
  return get<XhsWorkDomainResponse>("/xhs-work-domain");
}

export async function updateXhsWorkDomain(update: XhsWorkDomainUpdate): Promise<{ ok: boolean }> {
  return patch<{ ok: boolean }>("/xhs-work-domain", update);
}

export function wake(): Promise<BeingState> {
  return post<BeingState>("/lifecycle/wake");
}

export function sleep(): Promise<BeingState> {
  return post<BeingState>("/lifecycle/sleep");
}

export function fetchState(): Promise<BeingState> {
  return get<BeingState>("/state");
}

export function fetchMacConsoleStatus(): Promise<MacConsoleBootstrapStatus> {
  return get<MacConsoleBootstrapStatus>("/environment/mac-console");
}

export function fetchAutobio(): Promise<AutobioResponse> {
  return get<AutobioResponse>("/runtime/autobio");
}

export function fetchWorld(): Promise<InnerWorldState> {
  return get<InnerWorldState>("/world");
}
