import { get, post } from "./apiClient";

export type VrmGenerationStatus =
  | "queued"
  | "validating_spec"
  | "running_blender"
  | "exporting_vrm"
  | "completed"
  | "failed"
  | "cancelled";

export type VrmGenerationArtifacts = {
  spec_path?: string | null;
  output_vrm_path?: string | null;
  log_path?: string | null;
  remediation_capability_request_id?: string | null;
};

export type VrmGenerationJob = {
  job_id: string;
  prompt: string;
  status: VrmGenerationStatus;
  input_model_path?: string | null;
  artifacts: VrmGenerationArtifacts;
  error_code?: string | null;
  error_message?: string | null;
  created_at?: string;
  updated_at?: string;
};

export type VrmGenerationJobListResponse = {
  items: VrmGenerationJob[];
};

export type CreateVrmGenerationJobRequest = {
  prompt: string;
  input_model_path?: string | null;
  spec?: Record<string, unknown> | null;
};

export function createVrmGenerationJob(payload: CreateVrmGenerationJobRequest): Promise<VrmGenerationJob> {
  return post<VrmGenerationJob>("/vrm-generation/jobs", payload);
}

export function fetchVrmGenerationJob(jobId: string): Promise<VrmGenerationJob> {
  return get<VrmGenerationJob>(`/vrm-generation/jobs/${encodeURIComponent(jobId)}`);
}

export function cancelVrmGenerationJob(jobId: string): Promise<VrmGenerationJob> {
  return post<VrmGenerationJob>(`/vrm-generation/jobs/${encodeURIComponent(jobId)}/cancel`);
}

export function listVrmGenerationJobs(options: { limit?: number } = {}): Promise<VrmGenerationJobListResponse> {
  const params = new URLSearchParams();
  if (options.limit !== undefined) {
    params.set("limit", String(options.limit));
  }
  const query = params.toString();
  return get<VrmGenerationJobListResponse>(`/vrm-generation/jobs${query ? `?${query}` : ""}`);
}
