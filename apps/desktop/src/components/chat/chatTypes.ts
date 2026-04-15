import type { ChatRequestBody, MemoryEntryDisplay } from "../../lib/api";

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
  requestMessage?: string;
  retryRequestBody?: ChatRequestBody;
  relatedMemories?: MemoryEntryDisplay[];
  knowledgeReferences?: KnowledgeReference[];
  streamSequence?: number;
};

export type ChatSendOptions = {
  mcpServerIds?: string[];
};
