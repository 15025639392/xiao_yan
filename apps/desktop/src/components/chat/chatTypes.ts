import type { ChatReasoningState, ChatRequestBody, MemoryEntryDisplay } from "../../lib/api";

export type MemoryReference = {
  source: string;
  wing: string;
  room: string;
  similarity: number | null;
  excerpt: string;
};

// Message core: what the user and assistant actually said.
export type ChatEntryCore = {
  id: string;
  role: "user" | "assistant";
  content: string;
};

// Lifecycle: where this reply sits in the send/stream/fail flow.
export type ChatEntryLifecycle = {
  state?: "streaming" | "failed";
  streamSequence?: number;
  errorMessage?: string;
};

// Linkage: request/session identifiers used to stitch local and runtime events together.
export type ChatEntryLinkage = {
  requestKey?: string;
  reasoningSessionId?: string;
};

// Recovery: data needed to retry a user send or resume an interrupted assistant reply.
export type ChatEntryRecovery = {
  requestMessage?: string;
  retryRequestBody?: ChatRequestBody;
};

// Enrichments: optional context attached to a reply after generation.
export type ChatEntryEnrichments = {
  relatedMemories?: MemoryEntryDisplay[];
  memoryReferences?: MemoryReference[];
  reasoningState?: ChatReasoningState;
};

export type ChatEntry = ChatEntryCore &
  ChatEntryLifecycle &
  ChatEntryLinkage &
  ChatEntryRecovery &
  ChatEntryEnrichments;

export function isAssistantChatEntry(entry: ChatEntry): boolean {
  return entry.role === "assistant";
}

export function isUserChatEntry(entry: ChatEntry): boolean {
  return entry.role === "user";
}

export function hasRecoverableAssistantReply(entry: ChatEntry): boolean {
  return isAssistantChatEntry(entry) && entry.state === "failed" && Boolean(entry.requestMessage?.trim());
}

export function hasRetryableUserSend(entry: ChatEntry): boolean {
  return isUserChatEntry(entry) && entry.state === "failed";
}

export function hasMemoryReferences(entry: ChatEntry): boolean {
  return Boolean(entry.memoryReferences?.length);
}

export function hasRelatedMemories(entry: ChatEntry): boolean {
  return Boolean(entry.relatedMemories?.length);
}

export type ChatSendOptions = {
  mcpServerIds?: string[];
  continuousReasoningEnabled?: boolean;
  reasoningSessionId?: string;
};
