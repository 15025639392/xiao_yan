import type { ChatEntry } from "../ChatPanel";
import type { BeingState, PersonaProfile } from "../../lib/api";
import { fetchMessages, fetchState } from "../../lib/api";
import type { AppRealtimeEvent } from "../../lib/realtime";
import { syncMessagesFromRuntime } from "./chatRuntimeMessages";
import { applyRuntimeRealtimeEvent } from "./runtimeRealtimeUpdates";

export type InitialRuntimeData = {
  state: BeingState;
  messages: ChatEntry[] | null;
};

export async function loadInitialRuntimeData(initialRoute: string): Promise<InitialRuntimeData> {
  const nextState = await fetchState();

  if (initialRoute !== "chat") {
    return {
      state: nextState,
      messages: null,
    };
  }

  try {
    const nextMessages = await fetchMessages();
    return {
      state: nextState,
      messages: syncMessagesFromRuntime([], nextMessages.messages),
    };
  } catch {
    return {
      state: nextState,
      messages: null,
    };
  }
}

export type AppliedRuntimeEvent = {
  state: BeingState;
  messages: ChatEntry[];
  shouldSettleSending: boolean;
  error: string;
};

export function applyIncomingRuntimeEvent(currentMessages: ChatEntry[], event: AppRealtimeEvent): AppliedRuntimeEvent | null {
  const runtimeUpdate = applyRuntimeRealtimeEvent(currentMessages, event);
  if (!runtimeUpdate) {
    return null;
  }

  return {
    state: runtimeUpdate.state,
    messages: runtimeUpdate.messages,
    shouldSettleSending: runtimeUpdate.messages.some(
      (entry) => entry.role === "assistant" && entry.content.trim().length > 0,
    ),
    error: runtimeUpdate.error,
  };
}

export function getPersonaProfileFromRealtimeEvent(event: AppRealtimeEvent): PersonaProfile | null {
  const personaPayload =
    event.type === "snapshot" ? event.payload.persona : event.type === "persona_updated" ? event.payload : null;
  return personaPayload?.profile ?? null;
}
