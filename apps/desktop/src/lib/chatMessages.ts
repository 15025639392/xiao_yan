import type { ChatEntry } from "../components/ChatPanel";
import type { ChatHistoryMessage } from "./api";
import {
  findAssistantSessionMatchIndex,
  findInFlightAssistantMatchIndex,
  findLocalUserMatchIndex,
  findPreviousIncomingUserContent,
  findPreviousIncomingUserRequestKey,
} from "./chatMessageMatching";
import {
  applyAssistantEntryPatch,
  applyRuntimeMessagePatch,
  clearRuntimeTransientState,
  createAssistantEntry,
} from "./chatMessageMutations";

export function mergeMessages(current: ChatEntry[], incoming: ChatHistoryMessage[]): ChatEntry[] {
  const merged = [...current];
  const matchedIndexes = new Set<number>();

  incoming.forEach((message, index) => {
    const incomingMessageId = message.id;
    const incomingSessionId = message.session_id;
    const incomingReasoningSessionId = resolveIncomingReasoningSessionId(message);
    const incomingReasoningState = resolveIncomingReasoningState(message);
    const previousIncomingUserContent = findPreviousIncomingUserContent(incoming, index);
    const previousIncomingUserRequestKey = findPreviousIncomingUserRequestKey(merged, incoming, index);
    const incomingRequestKey = message.request_key ?? undefined;
    const linkedAssistantRequestKey =
      incomingRequestKey ?? (message.role === "assistant" ? previousIncomingUserRequestKey : undefined);
    const incomingRequestMessage =
      message.role === "assistant" ? (previousIncomingUserContent ?? undefined) : undefined;
    const exactMatchIndex =
      incomingMessageId == null ? -1 : merged.findIndex((entry) => entry.id === incomingMessageId);
    if (exactMatchIndex >= 0 && incomingMessageId != null) {
      merged[exactMatchIndex] = clearRuntimeTransientState(
        applyRuntimeMessagePatch(merged[exactMatchIndex], {
          id: incomingMessageId,
          role: message.role,
          content: message.content,
          requestKey: incomingRequestKey,
          reasoningSessionId: incomingReasoningSessionId,
          reasoningState: incomingReasoningState,
        }),
      );
      if (incomingRequestMessage && merged[exactMatchIndex].role === "assistant") {
        merged[exactMatchIndex] = {
          ...merged[exactMatchIndex],
          requestMessage: merged[exactMatchIndex].requestMessage ?? incomingRequestMessage,
        };
      }
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
      merged[sessionMatchIndex] = clearRuntimeTransientState(
        applyRuntimeMessagePatch(currentEntry, {
          id: keepStreamingId ? currentEntry.id : incomingMessageId ?? currentEntry.id,
          role: message.role,
          content: message.content,
          requestKey: incomingRequestKey,
          reasoningSessionId: incomingReasoningSessionId,
          reasoningState: incomingReasoningState,
        }),
      );
      if (incomingRequestMessage && merged[sessionMatchIndex].role === "assistant") {
        merged[sessionMatchIndex] = {
          ...merged[sessionMatchIndex],
          requestMessage: merged[sessionMatchIndex].requestMessage ?? incomingRequestMessage,
        };
      }
      matchedIndexes.add(sessionMatchIndex);
      return;
    }

    const localUserMatchIndex = findLocalUserMatchIndex(
      merged,
      matchedIndexes,
      message.role,
      message.content,
    );
    if (localUserMatchIndex >= 0) {
      merged[localUserMatchIndex] = clearRuntimeTransientState(
        applyRuntimeMessagePatch(merged[localUserMatchIndex], {
          id: incomingMessageId ?? merged[localUserMatchIndex].id,
          role: message.role,
          content: message.content,
          requestKey: incomingRequestKey,
        }),
      );
      matchedIndexes.add(localUserMatchIndex);
      return;
    }

    const fallbackMatchIndex = merged.findIndex(
      (entry, candidateIndex) =>
        !matchedIndexes.has(candidateIndex) &&
        entry.role === message.role &&
        entry.content === message.content,
    );
    if (fallbackMatchIndex >= 0) {
      merged[fallbackMatchIndex] = clearRuntimeTransientState(
        applyRuntimeMessagePatch(merged[fallbackMatchIndex], {
          id: incomingMessageId ?? merged[fallbackMatchIndex].id,
          role: message.role,
          content: message.content,
          requestKey: incomingRequestKey,
          reasoningSessionId: incomingReasoningSessionId,
          reasoningState: incomingReasoningState,
        }),
      );
      if (incomingRequestMessage && merged[fallbackMatchIndex].role === "assistant") {
        merged[fallbackMatchIndex] = {
          ...merged[fallbackMatchIndex],
          requestMessage: merged[fallbackMatchIndex].requestMessage ?? incomingRequestMessage,
        };
      }
      matchedIndexes.add(fallbackMatchIndex);
      return;
    }
    const inFlightMatchIndex = findInFlightAssistantMatchIndex(
      merged,
      matchedIndexes,
      message,
      previousIncomingUserContent,
      previousIncomingUserRequestKey,
    );
    if (inFlightMatchIndex >= 0) {
      const currentEntry = merged[inFlightMatchIndex];
      const keepStreamingId = currentEntry.state === "streaming" || currentEntry.state === "failed";
      merged[inFlightMatchIndex] = clearRuntimeTransientState(
        applyRuntimeMessagePatch(currentEntry, {
          id: keepStreamingId ? currentEntry.id : incomingMessageId ?? currentEntry.id,
          role: message.role,
          content: message.content,
          requestKey: incomingRequestKey,
          reasoningSessionId: incomingReasoningSessionId,
          reasoningState: incomingReasoningState,
        }),
      );
      if (incomingRequestMessage && merged[inFlightMatchIndex].role === "assistant") {
        merged[inFlightMatchIndex] = {
          ...merged[inFlightMatchIndex],
          requestMessage: merged[inFlightMatchIndex].requestMessage ?? incomingRequestMessage,
        };
      }
      matchedIndexes.add(inFlightMatchIndex);
      return;
    }

    if (message.role === "assistant") {
      merged.push(
        createAssistantEntry(incomingMessageId ?? `${message.role}-${merged.length}-${message.content}`, message.content, {
          requestKey: linkedAssistantRequestKey,
          requestMessage: incomingRequestMessage,
          reasoningSessionId: incomingReasoningSessionId,
          reasoningState: incomingReasoningState,
        }),
      );
    } else {
      merged.push(
        applyRuntimeMessagePatch(
          {
            id: incomingMessageId ?? `${message.role}-${merged.length}-${message.content}`,
            role: message.role,
            content: message.content,
          },
          {
            id: incomingMessageId ?? `${message.role}-${merged.length}-${message.content}`,
            role: message.role,
            content: message.content,
            requestKey: incomingRequestKey,
            reasoningSessionId: incomingReasoningSessionId,
            reasoningState: incomingReasoningState,
          },
        ),
      );
    }
    matchedIndexes.add(merged.length - 1);
  });

  return merged;
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
  requestKey?: string,
): ChatEntry[] {
  const existingIndex = findAssistantEntryIndex(current, assistantMessageId, requestKey, requestMessage);
  const existing = existingIndex >= 0 ? current[existingIndex] : undefined;
  if (existing) {
    return current.map((message) =>
      message.id === existing.id
        ? {
            ...applyAssistantEntryPatch(message, {
              content,
              state,
              requestKey,
              requestMessage,
              knowledgeReferences,
              reasoningSessionId,
              reasoningState,
              streamSequence: maxStreamSequence(message.streamSequence, sequence),
            }),
            id: assistantMessageId,
          }
        : message,
    );
  }

  return [
    ...current,
    createAssistantEntry(assistantMessageId, content, {
      state,
      requestKey,
      requestMessage,
      knowledgeReferences,
      reasoningSessionId,
      reasoningState,
      streamSequence: sequence,
    }),
  ];
}

export function appendAssistantDelta(
  current: ChatEntry[],
  assistantMessageId: string,
  delta: string,
  sequence?: number,
  reasoningSessionId?: string,
  reasoningState?: ChatEntry["reasoningState"],
  requestKey?: string,
): ChatEntry[] {
  const existingIndex = findAssistantEntryIndex(current, assistantMessageId, requestKey);
  const existing = existingIndex >= 0 ? current[existingIndex] : undefined;
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
      requestKey,
    );
  }

  if (!shouldApplyStreamSequence(existing.streamSequence, sequence)) {
    return current;
  }
  return current.map((message) =>
    message.id === existing.id
      ? {
          ...applyAssistantEntryPatch(message, {
            content: mergeAssistantStreamContent(message.content, delta, message.streamSequence, sequence),
            state: "streaming",
            requestKey,
            reasoningSessionId,
            reasoningState,
            streamSequence: maxStreamSequence(message.streamSequence, sequence),
          }),
          id: assistantMessageId,
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
  requestKey?: string,
): ChatEntry[] {
  const existingIndex = findAssistantEntryIndex(current, assistantMessageId, requestKey);
  const existing = existingIndex >= 0 ? current[existingIndex] : undefined;
  if (existing) {
    if (!shouldApplyStreamSequence(existing.streamSequence, sequence)) {
      return current;
    }

    // Preserve other fields (requestMessage, etc).
    return current.map((message) =>
      message.id === existing.id
        ? {
            ...applyAssistantEntryPatch(message, {
              content,
              state: undefined,
              requestKey,
              knowledgeReferences,
              reasoningSessionId,
              reasoningState,
              streamSequence: maxStreamSequence(message.streamSequence, sequence),
            }),
            id: assistantMessageId,
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
    requestKey,
  );
}

export function markAssistantMessageFailed(
  current: ChatEntry[],
  assistantMessageId: string,
  sequence?: number,
  reasoningSessionId?: string,
  reasoningState?: ChatEntry["reasoningState"],
  errorMessage?: string,
  requestKey?: string,
): ChatEntry[] {
  const existingIndex = findAssistantEntryIndex(current, assistantMessageId, requestKey);
  const existing = existingIndex >= 0 ? current[existingIndex] : undefined;
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
      requestKey,
    );
  }

  if (!shouldApplyStreamSequence(existing.streamSequence, sequence)) {
    return current;
  }

  return current.map((message) =>
    message.id === existing.id
      ? {
          ...applyAssistantEntryPatch(message, {
            state: "failed",
            errorMessage,
            requestKey,
            reasoningSessionId,
            reasoningState,
            streamSequence: maxStreamSequence(message.streamSequence, sequence),
          }),
          id: assistantMessageId,
        }
      : message,
  );
}

function findAssistantEntryIndex(
  current: ChatEntry[],
  assistantMessageId: string,
  requestKey?: string,
  requestMessage?: string,
): number {
  const exactIndex = current.findIndex((message) => message.id === assistantMessageId);
  if (exactIndex >= 0) {
    return exactIndex;
  }

  if (requestKey) {
    const requestKeyIndex = current.findIndex(
      (message) =>
        message.role === "assistant" &&
        message.requestKey === requestKey &&
        (message.state === "streaming" || message.state === "failed"),
    );
    if (requestKeyIndex >= 0) {
      return requestKeyIndex;
    }
  }

  if (requestMessage) {
    return current.findIndex(
      (message) =>
        message.role === "assistant" &&
        message.requestMessage === requestMessage &&
        (message.state === "streaming" || message.state === "failed"),
    );
  }

  return -1;
}

export function markAssistantMessageStreaming(current: ChatEntry[], assistantMessageId: string): ChatEntry[] {
  return current.map((message) =>
    message.id === assistantMessageId ? { ...message, state: "streaming", errorMessage: undefined } : message,
  );
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
