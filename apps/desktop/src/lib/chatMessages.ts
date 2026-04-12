import type { ChatEntry } from "../components/ChatPanel";
import type { ChatHistoryMessage } from "./api";

export function mergeMessages(current: ChatEntry[], incoming: ChatHistoryMessage[]): ChatEntry[] {
  const merged = [...current];
  const matchedIndexes = new Set<number>();

  incoming.forEach((message, index) => {
    const incomingMessageId = message.id;
    const incomingSessionId = message.session_id;
    const exactMatchIndex =
      incomingMessageId == null ? -1 : merged.findIndex((entry) => entry.id === incomingMessageId);
    if (exactMatchIndex >= 0 && incomingMessageId != null) {
      merged[exactMatchIndex] = {
        ...merged[exactMatchIndex],
        id: incomingMessageId,
        role: message.role,
        content: message.content,
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
      };
      matchedIndexes.add(inFlightMatchIndex);
      return;
    }

    merged.push({
      id: incomingMessageId ?? `${message.role}-${merged.length}-${message.content}`,
      role: message.role,
      content: message.content,
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

export function upsertAssistantMessage(
  current: ChatEntry[],
  assistantMessageId: string,
  content: string,
  state?: ChatEntry["state"],
  requestMessage?: string,
  sequence?: number,
  knowledgeReferences?: ChatEntry["knowledgeReferences"],
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
      streamSequence: sequence,
    },
  ];
}

export function appendAssistantDelta(
  current: ChatEntry[],
  assistantMessageId: string,
  delta: string,
  sequence?: number,
): ChatEntry[] {
  const existing = current.find((message) => message.id === assistantMessageId);
  if (!existing) {
    return upsertAssistantMessage(current, assistantMessageId, delta, "streaming", undefined, sequence);
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
  );
}

export function markAssistantMessageFailed(
  current: ChatEntry[],
  assistantMessageId: string,
  sequence?: number,
): ChatEntry[] {
  const existing = current.find((message) => message.id === assistantMessageId);
  if (!existing) {
    return upsertAssistantMessage(current, assistantMessageId, "", "failed", undefined, sequence);
  }

  if (!shouldApplyStreamSequence(existing.streamSequence, sequence)) {
    return current;
  }

  return current.map((message) =>
    message.id === assistantMessageId
      ? { ...message, state: "failed", streamSequence: maxStreamSequence(message.streamSequence, sequence) }
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
