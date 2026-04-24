export * from "./apiClient";
export * from "./apiConfig";
export * from "./apiMemory";
export * from "./apiPersona";
export * from "./apiRuntime";
export * from "./apiTools";
export * from "./apiVrmGeneration";
export * from "./apiXiaohongshu";

import { BASE_URL, buildHttpError, get, post, put } from "./apiClient";

export type ChatSubmissionResult = {
  response_id: string | null;
  assistant_message_id: string;
  reasoning_session_id?: string;
  reasoning_state?: ChatReasoningState;
};

export type ChatAttachment = {
  type: "folder" | "file" | "image";
  path: string;
  name?: string | null;
  mime_type?: string | null;
};

export type ChatReasoningRequest = {
  enabled: boolean;
  session_id?: string;
};

export type ChatReasoningState = {
  session_id: string;
  phase: "planning" | "exploring" | "finalizing" | "completed" | string;
  step_index: number;
  summary: string;
  updated_at: string;
};

export type ChatRequestBody = {
  message: string;
  request_key?: string;
  user_timezone?: string;
  user_local_time?: string;
  user_time_of_day?: "morning" | "afternoon" | "evening" | "night";
  attachments?: ChatAttachment[];
  mcp_servers?: string[];
  skills?: string[];
  reasoning?: ChatReasoningRequest;
};

export type FolderAccessLevel = "read_only" | "full_access";

export type ChatFolderPermission = {
  path: string;
  access_level: FolderAccessLevel;
};

export type ChatFolderPermissionsResponse = {
  permissions: ChatFolderPermission[];
};

export type ChatSkillEntry = {
  name: string;
  description?: string | null;
  path: string;
  trigger_prefixes: string[];
};

export type ChatSkillListResponse = {
  skills: ChatSkillEntry[];
};

export type ChatResumeRequest = {
  message: string;
  assistant_message_id: string;
  partial_content: string;
  request_key?: string;
  reasoning_session_id?: string;
  user_timezone?: string;
  user_local_time?: string;
  user_time_of_day?: "morning" | "afternoon" | "evening" | "night";
};

export type ChatHistoryMessage = {
  id?: string;
  role: "user" | "assistant";
  content: string;
  created_at?: string | null;
  session_id?: string | null;
  request_key?: string | null;
  reasoning_session_id?: string | null;
  reasoning_state?: ChatReasoningState | null;
};

export type ChatHistoryResponse = {
  messages: ChatHistoryMessage[];
  limit?: number | null;
  offset?: number | null;
  has_more?: boolean | null;
  next_offset?: number | null;
};

export type ChatMessagesPageParams = {
  limit?: number;
  offset?: number;
};

export function chat(messageOrBody: string | ChatRequestBody): Promise<ChatSubmissionResult> {
  if (typeof messageOrBody === "string") {
    return post<ChatSubmissionResult>("/chat", { message: messageOrBody });
  }
  return post<ChatSubmissionResult>("/chat", messageOrBody);
}

export function fetchChatFolderPermissions(): Promise<ChatFolderPermissionsResponse> {
  return get<ChatFolderPermissionsResponse>("/chat/folder-permissions");
}

export function fetchChatSkills(): Promise<ChatSkillListResponse> {
  return get<ChatSkillListResponse>("/chat/skills");
}

export function upsertChatFolderPermission(
  path: string,
  accessLevel: FolderAccessLevel,
): Promise<ChatFolderPermissionsResponse> {
  return put<ChatFolderPermissionsResponse>("/chat/folder-permissions", {
    path,
    access_level: accessLevel,
  });
}

export async function removeChatFolderPermission(path: string): Promise<ChatFolderPermissionsResponse> {
  const response = await fetch(`${BASE_URL}/chat/folder-permissions?path=${encodeURIComponent(path)}`, {
    method: "DELETE",
  });
  if (!response.ok) {
    throw await buildHttpError(response);
  }
  return response.json();
}

export function resumeChat(body: ChatResumeRequest): Promise<ChatSubmissionResult> {
  return post<ChatSubmissionResult>("/chat/resume", body);
}

export function fetchMessages(params?: ChatMessagesPageParams): Promise<ChatHistoryResponse> {
  const query = new URLSearchParams();
  if (typeof params?.limit === "number") {
    query.set("limit", String(params.limit));
  }
  if (typeof params?.offset === "number") {
    query.set("offset", String(params.offset));
  }
  const suffix = query.toString();
  const path = suffix ? `/messages?${suffix}` : "/messages";
  return get<ChatHistoryResponse>(path);
}
