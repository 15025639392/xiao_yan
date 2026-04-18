import type { ChatEntry } from "../ChatPanel";
import type { AppRealtimeEvent } from "../../lib/realtime";
import { applyChatRealtimeEvent } from "./chatRealtimeUpdates";
import { hasVisibleAssistantContent, shouldSettleSendingAfterChatEvent } from "./chatSendingState";
import type { PendingChatRequest } from "./chatRequestKey";

export type AppliedChatEvent = {
  messages: ChatEntry[];
  error: string;
  clearPendingRequest: boolean;
  shouldSettleSending: boolean;
};

export function applyIncomingChatEvent(
  currentMessages: ChatEntry[],
  event: AppRealtimeEvent,
  pendingRequest: PendingChatRequest | null,
): AppliedChatEvent | null {
  const chatUpdate = applyChatRealtimeEvent(currentMessages, event, pendingRequest);
  if (!chatUpdate) {
    return null;
  }

  return {
    messages: chatUpdate.messages,
    error: chatUpdate.error,
    clearPendingRequest: chatUpdate.clearPendingRequest,
    shouldSettleSending:
      shouldSettleSendingAfterChatEvent(event) || hasVisibleAssistantContent(chatUpdate.messages),
  };
}
