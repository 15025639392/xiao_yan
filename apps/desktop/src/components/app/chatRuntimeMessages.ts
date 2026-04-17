import type { ChatEntry } from "../ChatPanel";
import { mergeMessages } from "../../lib/chatMessages";

export function syncMessagesFromRuntime(
  current: ChatEntry[],
  incoming: Parameters<typeof mergeMessages>[1],
): ChatEntry[] {
  // Runtime payload contains full chat snapshot; empty list means messages were cleared.
  if (!Array.isArray(incoming) || incoming.length === 0) {
    // Keep local in-flight/failed assistant bubbles and unsynced local user input.
    // Also keep just-completed local assistant replies tied to unsynced local users.
    // This avoids transient runtime updates dropping fresh local conversation.
    const unsyncedUserContents = new Set(
      current
        .filter((entry) => entry.role === "user" && entry.id.startsWith("user-"))
        .map((entry) => entry.content),
    );

    return current.filter(
      (entry) =>
        entry.state === "streaming" ||
        entry.state === "failed" ||
        (entry.role === "user" && entry.id.startsWith("user-")) ||
        (entry.role === "assistant" &&
          entry.state == null &&
          Boolean(entry.requestMessage) &&
          unsyncedUserContents.has(entry.requestMessage ?? "")),
    );
  }

  return mergeMessages(current, incoming);
}
