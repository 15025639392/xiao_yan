import { get, post } from "./apiClient";

export type UpgradeProposalStatus =
  | "draft"
  | "submitted"
  | "approved"
  | "rejected"
  | "implemented"
  | "abandoned";

export type UpgradeProposalCategory =
  | "workflow_fix"
  | "habit_adjustment"
  | "new_capability"
  | "boundary_tuning";

export type UpgradeProposalPriority = "low" | "medium" | "high" | "critical";

export type UpgradeProposal = {
  proposal_id: string;
  created_at: string;
  status: UpgradeProposalStatus;
  her_voice: string;
  motivation: string;
  pain_points: string[];
  observed_data: Record<string, unknown>;
  category: UpgradeProposalCategory;
  target_domain: string;
  suggested_priority: UpgradeProposalPriority;
  expected_benefit?: string | null;
  risk_concern?: string | null;
  rollback_plan?: string | null;
  implemented_at?: string | null;
  observation_result?: "success" | "partial" | "failed" | "unknown" | null;
  observation_notes?: string | null;
  approved_at?: string | null;
  approved_by?: string | null;
  rejected_at?: string | null;
  rejected_by?: string | null;
  reject_reason?: string | null;
};

export type UpgradeProposalListResponse = {
  proposals: UpgradeProposal[];
  total: number;
};

export type UpgradeProposalActionResponse = {
  ok: boolean;
  proposal: UpgradeProposal | null;
  message?: string | null;
};

export function fetchUpgradeProposals(params: {
  status?: UpgradeProposalStatus;
  category?: UpgradeProposalCategory;
  targetDomain?: string;
  limit?: number;
} = {}): Promise<UpgradeProposalListResponse> {
  const query = new URLSearchParams();
  if (params.status) query.set("status", params.status);
  if (params.category) query.set("category", params.category);
  if (params.targetDomain) query.set("target_domain", params.targetDomain);
  if (typeof params.limit === "number") query.set("limit", String(params.limit));
  const suffix = query.toString();
  return get<UpgradeProposalListResponse>(suffix ? `/upgrade-proposals?${suffix}` : "/upgrade-proposals");
}

export function approveUpgradeProposal(proposalId: string): Promise<UpgradeProposalActionResponse> {
  return post<UpgradeProposalActionResponse>(
    `/upgrade-proposals/${encodeURIComponent(proposalId)}/approve`,
    { approver: "desktop" },
  );
}

export function rejectUpgradeProposal(proposalId: string, reason: string): Promise<UpgradeProposalActionResponse> {
  return post<UpgradeProposalActionResponse>(
    `/upgrade-proposals/${encodeURIComponent(proposalId)}/reject`,
    { approver: "desktop", reason },
  );
}

export function markUpgradeProposalImplemented(proposalId: string): Promise<UpgradeProposalActionResponse> {
  return post<UpgradeProposalActionResponse>(`/upgrade-proposals/${encodeURIComponent(proposalId)}/implement`);
}
