import type { ChatReasoningState, ChatRequestBody, MemoryEntryDisplay } from "../../lib/api";

export type KnowledgeReference = {
  source: string;
  wing: string;
  room: string;
  similarity: number | null;
  excerpt: string;
};

export type ChatEntry = {
  id: string;
  role: "user" | "assistant";
  content: string;
  state?: "streaming" | "failed";
  errorMessage?: string;
  requestKey?: string;
  requestMessage?: string;
  retryRequestBody?: ChatRequestBody;
  relatedMemories?: MemoryEntryDisplay[];
  knowledgeReferences?: KnowledgeReference[];
  reasoningSessionId?: string;
  reasoningState?: ChatReasoningState;
  streamSequence?: number;
};

export type ChatSendOptions = {
  mcpServerIds?: string[];
  continuousReasoningEnabled?: boolean;
  reasoningSessionId?: string;
};
