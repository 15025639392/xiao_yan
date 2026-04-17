import type { ChatEntry } from "../ChatPanel";
import type { AppRealtimeEvent } from "../../lib/realtime";

export function hasVisibleAssistantContent(messages: ChatEntry[]): boolean {
  return messages.some((message) => message.role === "assistant" && message.content.trim().length > 0);
}

export function shouldSettleSendingAfterChatEvent(event: AppRealtimeEvent): boolean {
  if (event.type === "chat_failed" || event.type === "chat_completed") {
    return true;
  }

  return event.type === "chat_delta" && event.payload.delta.trim().length > 0;
}
