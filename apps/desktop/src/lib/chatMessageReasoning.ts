import type { ChatEntry } from "../components/ChatPanel";
import type { ChatHistoryMessage } from "./api";

export function resolveIncomingReasoningSessionId(message: ChatHistoryMessage): string | undefined {
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

export function resolveIncomingReasoningState(message: ChatHistoryMessage): ChatEntry["reasoningState"] | undefined {
  if (message.role !== "assistant" || message.reasoning_state == null) {
    return undefined;
  }
  return message.reasoning_state;
}
