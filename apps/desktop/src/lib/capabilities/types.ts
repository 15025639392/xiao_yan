export type CapabilityName = "fs.read" | "fs.write" | "fs.list" | "fs.search" | "shell.run";

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
