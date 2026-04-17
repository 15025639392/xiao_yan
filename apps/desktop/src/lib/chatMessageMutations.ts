import type { ChatEntry } from "../components/chat/chatTypes";

export type AssistantEntryPatch = {
  content?: string;
  state?: ChatEntry["state"];
  errorMessage?: string;
  requestKey?: string;
  requestMessage?: string;
  knowledgeReferences?: ChatEntry["knowledgeReferences"];
  reasoningSessionId?: string;
  reasoningState?: ChatEntry["reasoningState"];
  streamSequence?: number;
};

export type RuntimeMessagePatch = {
  id: string;
  role: ChatEntry["role"];
  content: string;
  requestKey?: string;
  reasoningSessionId?: string;
  reasoningState?: ChatEntry["reasoningState"];
};

export function applyAssistantEntryPatch(entry: ChatEntry, patch: AssistantEntryPatch): ChatEntry {
  return {
    ...entry,
    content: patch.content || entry.content,
    state: patch.state,
    errorMessage: patch.errorMessage ?? entry.errorMessage,
    requestKey: patch.requestKey ?? entry.requestKey,
    requestMessage: patch.requestMessage ?? entry.requestMessage,
    knowledgeReferences: patch.knowledgeReferences ?? entry.knowledgeReferences,
    reasoningSessionId: patch.reasoningSessionId ?? entry.reasoningSessionId,
    reasoningState: patch.reasoningState ?? entry.reasoningState,
    streamSequence: patch.streamSequence ?? entry.streamSequence,
  };
}

export function createAssistantEntry(
  assistantMessageId: string,
  content: string,
  patch: AssistantEntryPatch = {},
): ChatEntry {
  return {
    id: assistantMessageId,
    role: "assistant",
    content,
    state: patch.state,
    errorMessage: patch.errorMessage,
    requestKey: patch.requestKey,
    requestMessage: patch.requestMessage,
    knowledgeReferences: patch.knowledgeReferences,
    reasoningSessionId: patch.reasoningSessionId,
    reasoningState: patch.reasoningState,
    streamSequence: patch.streamSequence,
  };
}

export function applyRuntimeMessagePatch(entry: ChatEntry, patch: RuntimeMessagePatch): ChatEntry {
  return {
    ...entry,
    id: patch.id,
    role: patch.role,
    content: patch.content,
    requestKey: patch.requestKey ?? entry.requestKey,
    reasoningSessionId: patch.reasoningSessionId ?? entry.reasoningSessionId,
    reasoningState: patch.reasoningState ?? entry.reasoningState,
  };
}

export function clearRuntimeTransientState(entry: ChatEntry): ChatEntry {
  if (entry.state == null && entry.errorMessage == null) {
    return entry;
  }

  return {
    ...entry,
    state: undefined,
    errorMessage: undefined,
  };
}
