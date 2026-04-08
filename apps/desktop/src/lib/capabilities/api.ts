import { BASE_URL } from "../api";
import type {
  CapabilityApprovalDecisionResponse,
  CapabilityApprovalHistoryResponse,
  CapabilityApprovalPendingResponse,
  CapabilityContractResponse,
  CapabilityDispatchRequest,
  CapabilityDispatchResponse,
  CapabilityJobAuditResponse,
  CapabilityJobStatus,
  CapabilityPendingResponse,
  CapabilityQueueStatusResponse,
  CapabilityResult,
} from "./types";

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`);
  if (!response.ok) {
    throw new Error(`request failed: ${response.status}`);
  }
  return response.json();
}

async function postJson<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    throw new Error(`request failed: ${response.status}`);
  }
  return response.json();
}

export function fetchCapabilityContract(): Promise<CapabilityContractResponse> {
  return getJson<CapabilityContractResponse>("/capabilities/contract");
}

export function dispatchCapability(request: CapabilityDispatchRequest): Promise<CapabilityDispatchResponse> {
  return postJson<CapabilityDispatchResponse>("/capabilities/dispatch", request);
}

export function fetchPendingCapabilities(executor = "desktop", limit = 3): Promise<CapabilityPendingResponse> {
  return getJson<CapabilityPendingResponse>(
    `/capabilities/pending?executor=${encodeURIComponent(executor)}&limit=${Math.max(1, limit)}`,
  );
}

export function completeCapability(result: CapabilityResult): Promise<{ request_id: string; status: string }> {
  return postJson<{ request_id: string; status: string }>("/capabilities/complete", result);
}

export function heartbeatCapabilityExecutor(executor = "desktop"): Promise<{ executor: string; heartbeat_at: string }> {
  return postJson<{ executor: string; heartbeat_at: string }>(
    `/capabilities/heartbeat?executor=${encodeURIComponent(executor)}`,
    {},
  );
}

type FetchCapabilityJobsParams = {
  limit?: number;
  status?: CapabilityJobStatus;
  deadLetterOnly?: boolean;
  approvalStatus?: "not_required" | "pending" | "approved" | "rejected";
  approver?: string;
  capability?: "fs.read" | "fs.write" | "fs.list" | "fs.search" | "shell.run";
  requestId?: string;
  cursor?: string;
};

export function fetchCapabilityQueueStatus(): Promise<CapabilityQueueStatusResponse> {
  return getJson<CapabilityQueueStatusResponse>("/capabilities/queue/status");
}

export function fetchCapabilityJobs(params: FetchCapabilityJobsParams = {}): Promise<CapabilityJobAuditResponse> {
  const query = new URLSearchParams();
  if (params.limit != null) {
    query.set("limit", String(Math.max(1, Math.min(200, params.limit))));
  }
  if (params.status) {
    query.set("status", params.status);
  }
  if (params.deadLetterOnly) {
    query.set("dead_letter_only", "true");
  }
  if (params.approvalStatus) {
    query.set("approval_status", params.approvalStatus);
  }
  if (params.approver) {
    query.set("approver", params.approver);
  }
  if (params.capability) {
    query.set("capability", params.capability);
  }
  if (params.requestId) {
    query.set("request_id", params.requestId);
  }
  if (params.cursor) {
    query.set("cursor", params.cursor);
  }

  const suffix = query.toString();
  return getJson<CapabilityJobAuditResponse>(`/capabilities/jobs${suffix ? `?${suffix}` : ""}`);
}

export function fetchCapabilityPendingApprovals(limit = 30): Promise<CapabilityApprovalPendingResponse> {
  const safeLimit = Math.max(1, Math.min(200, limit));
  return getJson<CapabilityApprovalPendingResponse>(`/capabilities/approvals/pending?limit=${safeLimit}`);
}

export function fetchCapabilityApprovalHistory(limit = 30): Promise<CapabilityApprovalHistoryResponse> {
  const safeLimit = Math.max(1, Math.min(200, limit));
  return getJson<CapabilityApprovalHistoryResponse>(`/capabilities/approvals/history?limit=${safeLimit}`);
}

export function approveCapabilityRequest(
  requestId: string,
  approver = "desktop-user",
): Promise<CapabilityApprovalDecisionResponse> {
  return postJson<CapabilityApprovalDecisionResponse>(
    `/capabilities/approvals/${encodeURIComponent(requestId)}/approve`,
    { approver },
  );
}

export function rejectCapabilityRequest(
  requestId: string,
  reason: string,
  approver = "desktop-user",
): Promise<CapabilityApprovalDecisionResponse> {
  return postJson<CapabilityApprovalDecisionResponse>(
    `/capabilities/approvals/${encodeURIComponent(requestId)}/reject`,
    { approver, reason },
  );
}
