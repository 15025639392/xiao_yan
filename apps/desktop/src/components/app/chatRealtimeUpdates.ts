import type { ChatEntry } from "../ChatPanel";
import {
  appendAssistantDelta,
  finalizeAssistantMessage,
  markAssistantMessageFailed,
  upsertAssistantMessage,
} from "../../lib/chatMessages";
import type { AppRealtimeEvent } from "../../lib/realtime";
import type { PendingChatRequest } from "./chatRequestKey";

export type ChatRealtimeUpdateResult = {
  messages: ChatEntry[];
  error: string;
  clearPendingRequest: boolean;
};

export function applyChatRealtimeEvent(
  current: ChatEntry[],
  event: AppRealtimeEvent,
  pendingRequest: PendingChatRequest | null,
): ChatRealtimeUpdateResult | null {
  if (event.type === "chat_started") {
    return {
      messages: upsertAssistantMessage(
        current,
        event.payload.assistant_message_id,
        "",
        "streaming",
        pendingRequest?.message,
        event.payload.sequence,
        undefined,
        event.payload.reasoning_session_id,
        event.payload.reasoning_state,
        event.payload.request_key ?? pendingRequest?.requestKey,
      ),
      error: "",
      clearPendingRequest: true,
    };
  }

  if (event.type === "chat_delta") {
    return {
      messages: appendAssistantDelta(
        current,
        event.payload.assistant_message_id,
        event.payload.delta,
        event.payload.sequence,
        event.payload.reasoning_session_id,
        event.payload.reasoning_state,
        event.payload.request_key,
      ),
      error: "",
      clearPendingRequest: false,
    };
  }

  if (event.type === "chat_completed") {
    return {
      messages: finalizeAssistantMessage(
        current,
        event.payload.assistant_message_id,
        event.payload.content,
        event.payload.sequence,
        event.payload.memory_references,
        event.payload.reasoning_session_id,
        event.payload.reasoning_state,
        event.payload.request_key,
      ),
      error: "",
      clearPendingRequest: false,
    };
  }

  if (event.type === "chat_failed") {
    return {
      messages: markAssistantMessageFailed(
        current,
        event.payload.assistant_message_id,
        event.payload.sequence,
        event.payload.reasoning_session_id,
        event.payload.reasoning_state,
        event.payload.error,
        event.payload.request_key,
      ),
      error: event.payload.error,
      clearPendingRequest: false,
    };
  }

  return null;
}
