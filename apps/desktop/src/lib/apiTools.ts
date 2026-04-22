import { get } from "./apiClient";

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

export function fetchTools(): Promise<ToolsListResponse> {
  return get<ToolsListResponse>("/tools");
}

export function fetchToolHistory(limit?: number): Promise<ToolsHistoryResponse> {
  return get<ToolsHistoryResponse>(`/tools/history?limit=${limit ?? 30}`);
}

export function clearToolHistory(): Promise<{ cleared: number; message: string }> {
  return fetch("/tools/history", { method: "DELETE" }).then((response) => response.json());
}

export function fetchToolsStatus(): Promise<ToolsStatusResponse> {
  return get<ToolsStatusResponse>("/tools/status");
}

export function readFile(path: string, maxBytes?: number): Promise<FileReadResult> {
  const params = `?path=${encodeURIComponent(path)}&max_bytes=${maxBytes ?? 512 * 1024}`;
  return get<FileReadResult>(`/tools/files/read${params}`);
}

export function listDirectory(path?: string, recursive?: boolean, pattern?: string | null): Promise<DirectoryListResult> {
  const params = new URLSearchParams();
  if (path) params.set("path", path);
  if (recursive) params.set("recursive", "true");
  if (pattern) params.set("pattern", pattern);
  return get<DirectoryListResult>(`/tools/files/list?${params.toString()}`);
}

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
