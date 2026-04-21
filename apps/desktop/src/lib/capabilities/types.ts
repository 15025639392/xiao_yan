export type CapabilityName =
  | "fs.read"
  | "fs.write"
  | "fs.list"
  | "fs.search"
  | "shell.run"
  | "browser.open"
  | "browser.snapshot"
  | "browser.extract"
  | "browser.close"
  | "browser.evaluate"
  | "browser.fill_form"
  | "browser.click_element"
  | "browser.publish"
  | "browser.find_publish_button";

export type RiskLevel = "safe" | "restricted" | "dangerous";

export type CapabilityJobStatus = "pending" | "in_progress" | "completed";

export type CapabilityApprovalStatus = "not_required" | "pending" | "approved" | "rejected";

export type CapabilityApprovalAction = "approved" | "rejected";

export type CapabilityContext = {
  goal_id?: string | null;
  reason?: string | null;
};

export type CapabilityRequest = {
  request_id: string;
  capability: CapabilityName;
  args: Record<string, unknown>;
  risk_level: RiskLevel;
  requires_approval: boolean;
  approval_status?: CapabilityApprovalStatus;
  approved_by?: string | null;
  approved_at?: string | null;
  rejected_by?: string | null;
  rejected_at?: string | null;
  rejection_reason?: string | null;
  attempt?: number;
  max_attempts?: number;
  context: CapabilityContext;
};

export type CapabilityAudit = {
  executor: string;
  started_at: string;
  finished_at: string;
  duration_ms: number;
};

export type CapabilityResult = {
  request_id: string;
  ok: boolean;
  output?: unknown;
  error_code?: string;
  error_message?: string;
  audit: CapabilityAudit;
};

export type CapabilityDescriptor = {
  name: CapabilityName;
  default_risk_level: RiskLevel;
  default_requires_approval: boolean;
  description: string;
  current_binding: string;
};

export type CapabilityContractResponse = {
  version: "v0";
  descriptors: CapabilityDescriptor[];
  request_schema: Record<string, unknown>;
  result_schema: Record<string, unknown>;
};

export type CapabilityDispatchRequest = {
  capability: CapabilityName;
  args?: Record<string, unknown>;
  risk_level?: RiskLevel;
  requires_approval?: boolean;
  context?: CapabilityContext;
};

export type CapabilityDispatchResponse = {
  request_id: string;
  status: CapabilityJobStatus;
  queued_at: string;
};

export type CapabilityPendingItem = {
  request: CapabilityRequest;
  queued_at: string;
  lease_expires_at: string;
};

export type CapabilityPendingResponse = {
  items: CapabilityPendingItem[];
};

export type CapabilityQueueStatusResponse = {
  pending: number;
  pending_approval: number;
  in_progress: number;
  completed: number;
  dead_letter: number;
};

export type CapabilityJobAuditItem = {
  request_id: string;
  capability: CapabilityName;
  status: CapabilityJobStatus;
  queued_at: string;
  completed_at?: string | null;
  attempt: number;
  max_attempts: number;
  approval_status: CapabilityApprovalStatus;
  policy_version?: string | null;
  policy_revision?: number | null;
  executor?: string | null;
  ok?: boolean | null;
  error_code?: string | null;
  dead_letter: boolean;
};

export type CapabilityJobAuditResponse = {
  items: CapabilityJobAuditItem[];
  next_cursor?: string | null;
};

export type CapabilityApprovalPendingItem = {
  request: CapabilityRequest;
  queued_at: string;
};

export type CapabilityApprovalPendingResponse = {
  items: CapabilityApprovalPendingItem[];
};

export type CapabilityApprovalHistoryItem = {
  request_id: string;
  capability: CapabilityName;
  action: CapabilityApprovalAction;
  approver: string;
  reason?: string | null;
  decided_at: string;
};

export type CapabilityApprovalHistoryResponse = {
  items: CapabilityApprovalHistoryItem[];
};

export type CapabilityApprovalDecisionResponse = {
  request_id: string;
  status: CapabilityJobStatus;
  approval_status: CapabilityApprovalStatus;
  completed_at?: string | null;
};

// Browser capability types

export type BrowserSessionStatus = "opening" | "active" | "idle" | "closing" | "closed" | "failed";

export type BrowserInteractionLevel = "read_only" | "interactive";

export type BrowserOpenArgs = {
  url: string;
  session_id?: string;
  headless?: boolean;
  wait_until?: string;
};

export type BrowserOpenOutput = {
  session_id: string;
  url: string;
  resolved_url: string;
  title: string;
  status: BrowserSessionStatus;
  opened_at: string;
};

export type BrowserSnapshotArgs = {
  session_id: string;
  include_text?: boolean;
  include_accessibility?: boolean;
  include_screenshot?: boolean;
  max_text_bytes?: number;
};

export type BrowserSnapshotOutput = {
  session_id: string;
  url: string;
  title: string;
  text_content: string;
  accessibility_tree: unknown;
  screenshot_path: string | null;
  captured_at: string;
};

export type BrowserExtractArgs = {
  session_id: string;
  target: string;
  schema?: Record<string, unknown>;
  max_items?: number;
};

export type BrowserExtractOutput = {
  session_id: string;
  target: string;
  content: string;
  structured_data: unknown;
  source_url: string;
  captured_at: string;
};

export type BrowserCloseArgs = {
  session_id: string;
};

export type BrowserCloseOutput = {
  session_id: string;
  closed_at: string;
  status: BrowserSessionStatus;
};
