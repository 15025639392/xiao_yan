import { BASE_URL } from "./api";
import type {
  BeingState,
  ChatHistoryMessage,
  EmotionState,
  Goal,
  InnerWorldState,
  MemoryEntryDisplay,
  MemorySummary,
  PersonaProfile,
} from "./api";

export type AppRuntimeRealtimePayload = {
  state: BeingState;
  messages: ChatHistoryMessage[];
  goals: Goal[];
  world: InnerWorldState | null;
  autobio: string[];
};

export type AppMemoryRealtimePayload = {
  summary: MemorySummary;
  timeline: MemoryEntryDisplay[];
};

export type AppPersonaRealtimePayload = {
  profile: PersonaProfile;
  emotion: EmotionState;
};

export type AppRealtimeSnapshot = {
  runtime: AppRuntimeRealtimePayload;
  memory: AppMemoryRealtimePayload;
  persona: AppPersonaRealtimePayload;
};

export type AppRealtimeEvent =
  | { type: "snapshot"; payload: AppRealtimeSnapshot }
  | { type: "runtime_updated"; payload: AppRuntimeRealtimePayload }
  | { type: "memory_updated"; payload: AppMemoryRealtimePayload }
  | { type: "persona_updated"; payload: AppPersonaRealtimePayload };

type AppRealtimeListener = (event: AppRealtimeEvent) => void;

const REALTIME_URL = `${BASE_URL.replace(/^http/, "ws")}/ws/app`;

let socket: WebSocket | null = null;
let reconnectTimer: number | null = null;
let reconnectDelayMs = 1000;
let latestSnapshot: AppRealtimeSnapshot | null = null;
const listeners = new Set<AppRealtimeListener>();

function resetRealtimeState(): void {
  listeners.clear();

  if (reconnectTimer != null) {
    window.clearTimeout(reconnectTimer);
    reconnectTimer = null;
  }

  latestSnapshot = null;
  reconnectDelayMs = 1000;

  if (socket && socket.readyState !== 3) {
    socket.close();
  }
  socket = null;
}

function ensureSocket(): void {
  if (typeof WebSocket === "undefined") {
    return;
  }
  if (socket && (socket.readyState === 0 || socket.readyState === 1)) {
    return;
  }

  socket = new WebSocket(REALTIME_URL);
  socket.onopen = () => {
    reconnectDelayMs = 1000;
  };
  socket.onmessage = (event) => {
    const payload = JSON.parse(String(event.data)) as AppRealtimeEvent;
    if (payload.type === "snapshot") {
      latestSnapshot = payload.payload;
    } else if (payload.type === "runtime_updated" && latestSnapshot) {
      latestSnapshot = { ...latestSnapshot, runtime: payload.payload };
    } else if (payload.type === "memory_updated" && latestSnapshot) {
      latestSnapshot = { ...latestSnapshot, memory: payload.payload };
    } else if (payload.type === "persona_updated" && latestSnapshot) {
      latestSnapshot = { ...latestSnapshot, persona: payload.payload };
    }

    listeners.forEach((listener) => listener(payload));
  };
  socket.onclose = () => {
    socket = null;
    if (listeners.size === 0) {
      return;
    }
    if (reconnectTimer != null) {
      window.clearTimeout(reconnectTimer);
    }
    reconnectTimer = window.setTimeout(() => {
      reconnectTimer = null;
      ensureSocket();
    }, reconnectDelayMs);
    reconnectDelayMs = Math.min(reconnectDelayMs * 2, 10000);
  };
}

export function subscribeAppRealtime(listener: AppRealtimeListener): () => void {
  listeners.add(listener);
  ensureSocket();

  if (latestSnapshot) {
    listener({ type: "snapshot", payload: latestSnapshot });
  }

  return () => {
    listeners.delete(listener);
    if (listeners.size === 0) {
      if (reconnectTimer != null) {
        window.clearTimeout(reconnectTimer);
        reconnectTimer = null;
      }
      if (socket && socket.readyState !== 3) {
        socket.close();
      }
      socket = null;
    }
  };
}

export function resetAppRealtimeForTests(): void {
  resetRealtimeState();
}
