import type { ChatEntry } from "../components/ChatPanel";
import type { ChatHistoryMessage } from "./api";

export function mergeMessages(current: ChatEntry[], incoming: ChatHistoryMessage[]): ChatEntry[] {
  const merged = [...current];
  const matchedIndexes = new Set<number>();

  incoming.forEach((message, index) => {
    const incomingMessageId = message.id;
    const incomingSessionId = message.session_id;
    const incomingReasoningSessionId = resolveIncomingReasoningSessionId(message);
    const incomingReasoningState = resolveIncomingReasoningState(message);
    const exactMatchIndex =
      incomingMessageId == null ? -1 : merged.findIndex((entry) => entry.id === incomingMessageId);
    if (exactMatchIndex >= 0 && incomingMessageId != null) {
      merged[exactMatchIndex] = {
        ...merged[exactMatchIndex],
        id: incomingMessageId,
        role: message.role,
        content: message.content,
        reasoningSessionId: incomingReasoningSessionId ?? merged[exactMatchIndex].reasoningSessionId,
        reasoningState: incomingReasoningState ?? merged[exactMatchIndex].reasoningState,
      };
      matchedIndexes.add(exactMatchIndex);
      return;
    }

    const sessionMatchIndex = findAssistantSessionMatchIndex(
      merged,
      matchedIndexes,
      message.role,
      incomingSessionId,
    );
    if (sessionMatchIndex >= 0) {
      const currentEntry = merged[sessionMatchIndex];
      const keepStreamingId = currentEntry.state === "streaming" || currentEntry.state === "failed";
      merged[sessionMatchIndex] = {
        ...currentEntry,
        id: keepStreamingId ? currentEntry.id : incomingMessageId ?? currentEntry.id,
        role: message.role,
        content: message.content,
        reasoningSessionId: incomingReasoningSessionId ?? currentEntry.reasoningSessionId,
        reasoningState: incomingReasoningState ?? currentEntry.reasoningState,
      };
      matchedIndexes.add(sessionMatchIndex);
      return;
    }

    const fallbackMatchIndex = merged.findIndex(
      (entry, candidateIndex) =>
        !matchedIndexes.has(candidateIndex) &&
        entry.role === message.role &&
        entry.content === message.content,
    );
    if (fallbackMatchIndex >= 0) {
      merged[fallbackMatchIndex] = {
        ...merged[fallbackMatchIndex],
        id: incomingMessageId ?? merged[fallbackMatchIndex].id,
        role: message.role,
        content: message.content,
        reasoningSessionId: incomingReasoningSessionId ?? merged[fallbackMatchIndex].reasoningSessionId,
        reasoningState: incomingReasoningState ?? merged[fallbackMatchIndex].reasoningState,
      };
      matchedIndexes.add(fallbackMatchIndex);
      return;
    }

    const previousIncomingUserContent = findPreviousIncomingUserContent(incoming, index);
    const inFlightMatchIndex = findInFlightAssistantMatchIndex(
      merged,
      matchedIndexes,
      message,
      previousIncomingUserContent,
    );
    if (inFlightMatchIndex >= 0) {
      const currentEntry = merged[inFlightMatchIndex];
      const keepStreamingId = currentEntry.state === "streaming" || currentEntry.state === "failed";
      merged[inFlightMatchIndex] = {
        ...currentEntry,
        id: keepStreamingId ? currentEntry.id : incomingMessageId ?? currentEntry.id,
        role: message.role,
        content: message.content,
        reasoningSessionId: incomingReasoningSessionId ?? currentEntry.reasoningSessionId,
        reasoningState: incomingReasoningState ?? currentEntry.reasoningState,
      };
      matchedIndexes.add(inFlightMatchIndex);
      return;
    }

    merged.push({
      id: incomingMessageId ?? `${message.role}-${merged.length}-${message.content}`,
      role: message.role,
      content: message.content,
      reasoningSessionId: incomingReasoningSessionId,
      reasoningState: incomingReasoningState,
    });
    matchedIndexes.add(merged.length - 1);
  });

  return merged;
}

function findAssistantSessionMatchIndex(
  current: ChatEntry[],
  matchedIndexes: Set<number>,
  role: ChatHistoryMessage["role"],
  sessionId: string | null | undefined,
): number {
  if (role !== "assistant" || !sessionId) {
    return -1;
  }

  return current.findIndex(
    (entry, index) => !matchedIndexes.has(index) && entry.role === "assistant" && entry.id === sessionId,
  );
}

function findPreviousIncomingUserContent(incoming: ChatHistoryMessage[], currentIndex: number): string | null {
  for (let index = currentIndex - 1; index >= 0; index -= 1) {
    if (incoming[index].role === "user") {
      return incoming[index].content;
    }
  }

  return null;
}

function findInFlightAssistantMatchIndex(
  current: ChatEntry[],
  matchedIndexes: Set<number>,
  incoming: ChatHistoryMessage,
  previousIncomingUserContent: string | null,
): number {
  if (incoming.role !== "assistant") {
    return -1;
  }

  for (let index = current.length - 1; index >= 0; index -= 1) {
    const entry = current[index];
    if (matchedIndexes.has(index)) {
      continue;
    }
    if (entry.role !== "assistant") {
      continue;
    }
    const isInFlight = entry.state === "streaming" || entry.state === "failed";

    // Runtime snapshots may arrive after local streaming is already finalized.
    // If this assistant bubble is still a local one tied to the same request,
    // reconcile it instead of appending a duplicate assistant reply.
    if (
      previousIncomingUserContent != null &&
      entry.requestMessage != null &&
      entry.requestMessage === previousIncomingUserContent &&
      (isInFlight || entry.id.startsWith("assistant_"))
    ) {
      return index;
    }

    if (!isInFlight) {
      continue;
    }
    if (
      previousIncomingUserContent != null &&
      entry.requestMessage != null &&
      entry.requestMessage === previousIncomingUserContent
    ) {
      return index;
    }
    if (incoming.content.startsWith(entry.content) || entry.content.startsWith(incoming.content)) {
      return index;
    }
  }

  return -1;
}

function resolveIncomingReasoningSessionId(message: ChatHistoryMessage): string | undefined {
  if (message.role !== "assistant") {
    return undefined;
  }
  const directSessionId =
    typeof message.reasoning_session_id === "string" ? message.reasoning_session_id.trim() : "";
  if (directSessionId) {
    return directSessionId;
  }
  const fromStateSessionId =
    message.reasoning_state != null && typeof message.reasoning_state.session_id === "string"
      ? message.reasoning_state.session_id.trim()
      : "";
  return fromStateSessionId || undefined;
}

function resolveIncomingReasoningState(message: ChatHistoryMessage): ChatEntry["reasoningState"] | undefined {
  if (message.role !== "assistant" || message.reasoning_state == null) {
    return undefined;
  }
  return message.reasoning_state;
}

export function upsertAssistantMessage(
  current: ChatEntry[],
  assistantMessageId: string,
  content: string,
  state?: ChatEntry["state"],
  requestMessage?: string,
  sequence?: number,
  knowledgeReferences?: ChatEntry["knowledgeReferences"],
  reasoningSessionId?: string,
  reasoningState?: ChatEntry["reasoningState"],
): ChatEntry[] {
  const existing = current.find((message) => message.id === assistantMessageId);
  if (existing) {
    return current.map((message) =>
      message.id === assistantMessageId
        ? {
            ...message,
            content: content || message.content,
            state,
            requestMessage: requestMessage ?? message.requestMessage,
            knowledgeReferences: knowledgeReferences ?? message.knowledgeReferences,
            reasoningSessionId: reasoningSessionId ?? message.reasoningSessionId,
            reasoningState: reasoningState ?? message.reasoningState,
            streamSequence: maxStreamSequence(message.streamSequence, sequence),
          }
        : message,
    );
  }

  return [
    ...current,
    {
      id: assistantMessageId,
      role: "assistant",
      content,
      state,
      requestMessage,
      knowledgeReferences,
      reasoningSessionId,
      reasoningState,
      streamSequence: sequence,
    },
  ];
}

export function appendAssistantDelta(
  current: ChatEntry[],
  assistantMessageId: string,
  delta: string,
  sequence?: number,
  reasoningSessionId?: string,
  reasoningState?: ChatEntry["reasoningState"],
): ChatEntry[] {
  const existing = current.find((message) => message.id === assistantMessageId);
  if (!existing) {
    return upsertAssistantMessage(
      current,
      assistantMessageId,
      delta,
      "streaming",
      undefined,
      sequence,
      undefined,
      reasoningSessionId,
      reasoningState,
    );
  }

  if (!shouldApplyStreamSequence(existing.streamSequence, sequence)) {
    return current;
  }
  return current.map((message) =>
    message.id === assistantMessageId
      ? {
          ...message,
          content: mergeAssistantStreamContent(message.content, delta, message.streamSequence, sequence),
          state: "streaming",
          reasoningSessionId: reasoningSessionId ?? message.reasoningSessionId,
          reasoningState: reasoningState ?? message.reasoningState,
          streamSequence: maxStreamSequence(message.streamSequence, sequence),
        }
      : message,
  );
}

function mergeAssistantStreamContent(
  currentContent: string,
  delta: string,
  currentSequence?: number,
  incomingSequence?: number,
): string {
  if (!shouldApplyStreamSequence(currentSequence, incomingSequence)) {
    return currentContent;
  }

  if (!currentContent) {
    return delta;
  }

  if (!delta) {
    return currentContent;
  }

  // Some compatible gateways send cumulative text snapshots instead of pure deltas.
  if (delta.startsWith(currentContent)) {
    return delta;
  }

  if (currentContent.startsWith(delta) || currentContent.includes(delta)) {
    return currentContent;
  }

  const maxOverlap = Math.min(currentContent.length, delta.length);
  for (let overlap = maxOverlap; overlap > 0; overlap -= 1) {
    if (currentContent.slice(-overlap) === delta.slice(0, overlap)) {
      return `${currentContent}${delta.slice(overlap)}`;
    }
  }

  return `${currentContent}${delta}`;
}

export function finalizeAssistantMessage(
  current: ChatEntry[],
  assistantMessageId: string,
  content: string,
  sequence?: number,
  knowledgeReferences?: ChatEntry["knowledgeReferences"],
  reasoningSessionId?: string,
  reasoningState?: ChatEntry["reasoningState"],
): ChatEntry[] {
  const existing = current.find((message) => message.id === assistantMessageId);
  if (existing) {
    if (!shouldApplyStreamSequence(existing.streamSequence, sequence)) {
      return current;
    }

    // Preserve other fields (requestMessage, etc).
    return current.map((message) =>
      message.id === assistantMessageId
        ? {
            ...message,
            content: content || message.content,
            state: undefined,
            knowledgeReferences: knowledgeReferences ?? message.knowledgeReferences,
            reasoningSessionId: reasoningSessionId ?? message.reasoningSessionId,
            reasoningState: reasoningState ?? message.reasoningState,
            streamSequence: maxStreamSequence(message.streamSequence, sequence),
          }
        : message,
    );
  }

  return upsertAssistantMessage(
    current,
    assistantMessageId,
    content,
    undefined,
    undefined,
    sequence,
    knowledgeReferences,
    reasoningSessionId,
    reasoningState,
  );
}

export function markAssistantMessageFailed(
  current: ChatEntry[],
  assistantMessageId: string,
  sequence?: number,
  reasoningSessionId?: string,
  reasoningState?: ChatEntry["reasoningState"],
): ChatEntry[] {
  const existing = current.find((message) => message.id === assistantMessageId);
  if (!existing) {
    return upsertAssistantMessage(
      current,
      assistantMessageId,
      "",
      "failed",
      undefined,
      sequence,
      undefined,
      reasoningSessionId,
      reasoningState,
    );
  }

  if (!shouldApplyStreamSequence(existing.streamSequence, sequence)) {
    return current;
  }

  return current.map((message) =>
    message.id === assistantMessageId
      ? {
          ...message,
          state: "failed",
          reasoningSessionId: reasoningSessionId ?? message.reasoningSessionId,
          reasoningState: reasoningState ?? message.reasoningState,
          streamSequence: maxStreamSequence(message.streamSequence, sequence),
        }
      : message,
  );
}

export function markAssistantMessageStreaming(current: ChatEntry[], assistantMessageId: string): ChatEntry[] {
  return current.map((message) => (message.id === assistantMessageId ? { ...message, state: "streaming" } : message));
}

function shouldApplyStreamSequence(currentSequence?: number, incomingSequence?: number): boolean {
  if (incomingSequence == null || currentSequence == null) {
    return true;
  }

  return incomingSequence > currentSequence;
}

function maxStreamSequence(currentSequence?: number, incomingSequence?: number): number | undefined {
  if (incomingSequence == null) {
    return currentSequence;
  }
  if (currentSequence == null) {
    return incomingSequence;
  }
  return Math.max(currentSequence, incomingSequence);
}
