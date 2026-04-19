import type { Dispatch, MutableRefObject, SetStateAction } from "react";

import type { ChatEntry } from "../ChatPanel";
import type { PendingChatRequest } from "./chatRequestKey";
import { applyIncomingChatEvent } from "./chatSync";
import { hasVisibleAssistantContent } from "./chatSendingState";
import {
  applyIncomingRuntimeEvent,
  getPersonaProfileFromRealtimeEvent,
  type InitialRuntimeData,
} from "./runtimeSync";
import type { BeingState, PersonaProfile } from "../../lib/api";
import type { AppRealtimeEvent } from "../../lib/realtime";

type SharedSetters = {
  setError: Dispatch<SetStateAction<string>>;
  setIsSending: Dispatch<SetStateAction<boolean>>;
  setMessages: Dispatch<SetStateAction<ChatEntry[]>>;
  setPersona: Dispatch<SetStateAction<PersonaProfile | null>>;
  setState: Dispatch<SetStateAction<BeingState>>;
};

export function applyInitialRuntimeData(
  initialRuntime: InitialRuntimeData,
  messagesRef: MutableRefObject<ChatEntry[]>,
  setters: Pick<SharedSetters, "setMessages" | "setState">,
) {
  setters.setState(initialRuntime.state);
  if (initialRuntime.messages) {
    messagesRef.current = initialRuntime.messages;
    setters.setMessages(initialRuntime.messages);
  }
}

export function handleChatRealtimeEvent(
  event: AppRealtimeEvent,
  messagesRef: MutableRefObject<ChatEntry[]>,
  pendingRequestMessageRef: MutableRefObject<PendingChatRequest | null>,
  setters: Pick<SharedSetters, "setError" | "setIsSending" | "setMessages">,
): boolean {
  if (
    event.type !== "chat_started" &&
    event.type !== "chat_delta" &&
    event.type !== "chat_completed" &&
    event.type !== "chat_failed"
  ) {
    return false;
  }

  const chatUpdate = applyIncomingChatEvent(
    messagesRef.current,
    event,
    pendingRequestMessageRef.current,
  );
  const nextMessages = chatUpdate?.messages ?? messagesRef.current;
  messagesRef.current = nextMessages;
  setters.setMessages(nextMessages);
  if (chatUpdate?.clearPendingRequest) {
    pendingRequestMessageRef.current = null;
  }
  if (chatUpdate?.shouldSettleSending) {
    setters.setIsSending(false);
  }
  setters.setError(chatUpdate?.error ?? "");
  return true;
}

export function handleRuntimeRealtimeEvent(
  event: AppRealtimeEvent,
  messagesRef: MutableRefObject<ChatEntry[]>,
  setters: Pick<
    SharedSetters,
    "setError" | "setIsSending" | "setMessages" | "setState"
  >,
): boolean {
  const runtimeUpdate = applyIncomingRuntimeEvent(messagesRef.current, event);
  if (!runtimeUpdate) {
    return false;
  }

  messagesRef.current = runtimeUpdate.messages;
  setters.setState(runtimeUpdate.state);
  setters.setMessages(runtimeUpdate.messages);
  if (runtimeUpdate.shouldSettleSending || hasVisibleAssistantContent(runtimeUpdate.messages)) {
    setters.setIsSending(false);
  }
  setters.setError(runtimeUpdate.error);
  return true;
}

export function handlePersonaRealtimeEvent(
  event: AppRealtimeEvent,
  setters: Pick<SharedSetters, "setPersona">,
): boolean {
  const personaProfile = getPersonaProfileFromRealtimeEvent(event);
  if (!personaProfile) {
    return false;
  }

  setters.setPersona(personaProfile);
  return true;
}
