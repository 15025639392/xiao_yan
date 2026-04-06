import type { MemoryEntryDisplay } from "../../lib/api";

export type ChatEntry = {
  id: string;
  role: "user" | "assistant";
  content: string;
  state?: "streaming" | "failed";
  requestMessage?: string;
  relatedMemories?: MemoryEntryDisplay[];
  streamSequence?: number;
};

