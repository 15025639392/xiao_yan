import { BASE_URL, get, post, put } from "./apiClient";

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

export function fetchMemorySummary(): Promise<MemorySummary> {
  return get<MemorySummary>("/memory/summary");
}

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

export function fetchKnowledgeSummary(): Promise<KnowledgeSummaryResponse> {
  return get<KnowledgeSummaryResponse>("/knowledge/summary");
}

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

export function reviewKnowledgeItemsBatch(data: {
  knowledge_ids: string[];
  decision: "approve" | "reject" | "pend";
  reviewer?: string | null;
  review_note?: string | null;
}): Promise<KnowledgeBatchReviewResponse> {
  return post<KnowledgeBatchReviewResponse>("/knowledge/items/review-batch", data);
}

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

export function searchMemories(query: string, limit?: number): Promise<MemorySearchResult> {
  return get<MemorySearchResult>(`/memory/search?q=${encodeURIComponent(query)}&limit=${limit ?? 10}`);
}

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

export function deleteMemory(memoryId: string): Promise<{ success: boolean; deleted_id: string }> {
  return fetch(`${BASE_URL}/memory/${encodeURIComponent(memoryId)}`, { method: "DELETE" }).then((response) => {
    if (!response.ok) {
      throw new Error(`delete memory failed: ${response.status}`);
    }
    return response.json();
  });
}

export function batchDeleteMemories(
  memoryIds: string[],
): Promise<{ success: boolean; deleted: number; failed: number; total: number }> {
  return post<{ success: boolean; deleted: number; failed: number; total: number }>(
    "/memory/batch-delete",
    { memory_ids: memoryIds },
  );
}

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

export function starMemory(
  memoryId: string,
  important: boolean = true,
): Promise<{ success: boolean; starred: boolean; memory_id: string }> {
  return post<{ success: boolean; starred: boolean; memory_id: string }>(
    `/memory/${encodeURIComponent(memoryId)}/star`,
    { important },
  );
}
