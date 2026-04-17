import type { ChatEntry } from "../ChatPanel";
import type { AppRealtimeEvent, AppRuntimeRealtimePayload } from "../../lib/realtime";
import { syncMessagesFromRuntime } from "./chatRuntimeMessages";

export type RuntimeRealtimeUpdateResult = {
  state: AppRuntimeRealtimePayload["state"];
  messages: ChatEntry[];
  goals: AppRuntimeRealtimePayload["goals"];
  world: AppRuntimeRealtimePayload["world"];
  macConsoleStatus: AppRuntimeRealtimePayload["mac_console_status"] | undefined;
  error: string;
};

export function getRuntimeRealtimePayload(
  event: AppRealtimeEvent,
): AppRuntimeRealtimePayload | null {
  if (event.type === "snapshot") {
    return event.payload.runtime;
  }

  if (event.type === "runtime_updated") {
    return event.payload;
  }

  return null;
}

export function applyRuntimeRealtimeEvent(
  currentMessages: ChatEntry[],
  event: AppRealtimeEvent,
): RuntimeRealtimeUpdateResult | null {
  const payload = getRuntimeRealtimePayload(event);
  if (!payload) {
    return null;
  }

  return {
    state: payload.state,
    messages: syncMessagesFromRuntime(currentMessages, payload.messages),
    goals: payload.goals,
    world: payload.world,
    macConsoleStatus: payload.mac_console_status,
    error: "",
  };
}
