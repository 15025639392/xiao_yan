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
