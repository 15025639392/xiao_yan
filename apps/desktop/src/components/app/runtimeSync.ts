import type { ChatEntry } from "../ChatPanel";
import type { BeingState, Goal, InnerWorldState, MacConsoleBootstrapStatus, PersonaProfile } from "../../lib/api";
import { fetchGoals, fetchMessages, fetchState, fetchWorld } from "../../lib/api";
import type { AppRealtimeEvent } from "../../lib/realtime";
import { syncMessagesFromRuntime } from "./chatRuntimeMessages";
import { applyRuntimeRealtimeEvent } from "./runtimeRealtimeUpdates";

export type InitialRuntimeData = {
  state: BeingState;
  goals: Goal[];
  world: InnerWorldState | null;
  messages: ChatEntry[] | null;
};

export async function loadInitialRuntimeData(initialRoute: string): Promise<InitialRuntimeData> {
  const [nextState, nextGoals, nextWorld] = await Promise.all([
    fetchState(),
    fetchGoals(),
    fetchWorld(),
  ]);

  if (initialRoute !== "chat") {
    return {
      state: nextState,
      goals: nextGoals.goals,
      world: nextWorld,
      messages: null,
    };
  }

  try {
    const nextMessages = await fetchMessages();
    return {
      state: nextState,
      goals: nextGoals.goals,
      world: nextWorld,
      messages: syncMessagesFromRuntime([], nextMessages.messages),
    };
  } catch {
    return {
      state: nextState,
      goals: nextGoals.goals,
      world: nextWorld,
      messages: null,
    };
  }
}

export type AppliedRuntimeEvent = {
  state: BeingState;
  messages: ChatEntry[];
  goals: Goal[];
  world: InnerWorldState | null;
  macConsoleStatus: MacConsoleBootstrapStatus | null | undefined;
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
    goals: runtimeUpdate.goals,
    world: runtimeUpdate.world,
    macConsoleStatus: runtimeUpdate.macConsoleStatus,
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
