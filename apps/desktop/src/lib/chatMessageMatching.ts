import type { ChatEntry } from "../components/ChatPanel";
import type { ChatHistoryMessage } from "./api";

export function findAssistantSessionMatchIndex(
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

export function findPreviousIncomingUserContent(
  incoming: ChatHistoryMessage[],
  currentIndex: number,
): string | null {
  for (let index = currentIndex - 1; index >= 0; index -= 1) {
    if (incoming[index].role === "user") {
      return incoming[index].content;
    }
  }

  return null;
}

export function findLocalUserMatchIndex(
  current: ChatEntry[],
  matchedIndexes: Set<number>,
  role: ChatHistoryMessage["role"],
  content: string,
): number {
  if (role !== "user") {
    return -1;
  }

  return current.findIndex(
    (entry, index) =>
      !matchedIndexes.has(index) &&
      entry.role === "user" &&
      entry.id.startsWith("user-") &&
      entry.content === content,
  );
}

export function findPreviousIncomingUserRequestKey(
  current: ChatEntry[],
  incoming: ChatHistoryMessage[],
  currentIndex: number,
): string | undefined {
  for (let index = currentIndex - 1; index >= 0; index -= 1) {
    const incomingMessage = incoming[index];
    if (incomingMessage.role !== "user") {
      continue;
    }

    const matchedEntry = current.find((entry) => {
      if (entry.role !== "user") {
        return false;
      }
      if (incomingMessage.id != null && entry.id === incomingMessage.id) {
        return true;
      }
      return entry.content === incomingMessage.content;
    });

    if (matchedEntry?.requestKey) {
      return matchedEntry.requestKey;
    }
  }

  return undefined;
}

export function findInFlightAssistantMatchIndex(
  current: ChatEntry[],
  matchedIndexes: Set<number>,
  incoming: ChatHistoryMessage,
  previousIncomingUserContent: string | null,
  previousIncomingUserRequestKey: string | undefined,
): number {
  if (incoming.role !== "assistant") {
    return -1;
  }

  for (let index = current.length - 1; index >= 0; index -= 1) {
    const entry = current[index];
    if (matchedIndexes.has(index) || entry.role !== "assistant") {
      continue;
    }

    const isInFlight = entry.state === "streaming" || entry.state === "failed";
    const requestKeyMatches =
      previousIncomingUserRequestKey != null &&
      entry.requestKey != null &&
      entry.requestKey === previousIncomingUserRequestKey;

    if (
      (requestKeyMatches ||
        (previousIncomingUserContent != null &&
          entry.requestMessage != null &&
          entry.requestMessage === previousIncomingUserContent)) &&
      (isInFlight || entry.id.startsWith("assistant_"))
    ) {
      return index;
    }

    if (!isInFlight) {
      continue;
    }
    if (requestKeyMatches) {
      return index;
    }
    if (previousIncomingUserContent != null && entry.requestMessage === previousIncomingUserContent) {
      return index;
    }
    if (incoming.content.startsWith(entry.content) || entry.content.startsWith(incoming.content)) {
      return index;
    }
  }

  return -1;
}
