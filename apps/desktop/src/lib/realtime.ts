import { BASE_URL } from "./api";
import type {
  BeingState,
  ChatHistoryMessage,
  ChatReasoningState,
  EmotionState,
  InnerWorldState,
  MacConsoleBootstrapStatus,
  MemoryEntryDisplay,
  MemorySummary,
  PersonaProfile,
  RelationshipSummary,
} from "./api";

export type AppRuntimeRealtimePayload = {
  state: BeingState;
  messages: ChatHistoryMessage[];
  world: InnerWorldState | null;
  autobio: string[];
  mac_console_status?: MacConsoleBootstrapStatus | null;
};

export type AppMemoryRealtimePayload = {
  summary: MemorySummary;
  relationship: RelationshipSummary;
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

export type AppChatStartedPayload = {
  assistant_message_id: string;
  response_id: string | null;
  request_key?: string;
  reasoning_session_id?: string;
  reasoning_state?: ChatReasoningState;
  session_id?: string;
  sequence?: number;
  timestamp_ms?: number;
};

export type AppChatDeltaPayload = {
  assistant_message_id: string;
  delta: string;
  request_key?: string;
  reasoning_session_id?: string;
  reasoning_state?: ChatReasoningState;
  session_id?: string;
  sequence?: number;
  timestamp_ms?: number;
};

export type AppMemoryReferencePayload = {
  source: string;
  wing: string;
  room: string;
  similarity: number | null;
  excerpt: string;
};

export type AppChatCompletedPayload = {
  assistant_message_id: string;
  response_id: string | null;
  content: string;
  request_key?: string;
  memory_references?: AppMemoryReferencePayload[];
  reasoning_session_id?: string;
  reasoning_state?: ChatReasoningState;
  session_id?: string;
  sequence?: number;
  timestamp_ms?: number;
};

export type AppChatFailedPayload = {
  assistant_message_id: string;
  error: string;
  request_key?: string;
  reasoning_session_id?: string;
  reasoning_state?: ChatReasoningState;
  session_id?: string;
  sequence?: number;
  timestamp_ms?: number;
};

export type AppRealtimeEvent =
  | { type: "snapshot"; payload: AppRealtimeSnapshot }
  | { type: "runtime_updated"; payload: AppRuntimeRealtimePayload }
  | { type: "memory_updated"; payload: AppMemoryRealtimePayload }
  | { type: "persona_updated"; payload: AppPersonaRealtimePayload }
  | { type: "chat_started"; payload: AppChatStartedPayload }
  | { type: "chat_delta"; payload: AppChatDeltaPayload }
  | { type: "chat_completed"; payload: AppChatCompletedPayload }
  | { type: "chat_failed"; payload: AppChatFailedPayload };

type AppRealtimeListener = (event: AppRealtimeEvent) => void;

const REALTIME_URL = `${BASE_URL.replace(/^http/, "ws")}/ws/app`;

let socket: WebSocket | null = null;
let reconnectTimer: number | null = null;
let reconnectDelayMs = 1000;
let latestSnapshot: AppRealtimeSnapshot | null = null;
const listeners = new Set<AppRealtimeListener>();
const chatEventState = new Map<
  string,
  {
    lastProcessedSequence: number;
    pendingEvents: Map<number, AppRealtimeEvent>;
  }
>();

function resetRealtimeState(): void {
  listeners.clear();

  if (reconnectTimer != null) {
    window.clearTimeout(reconnectTimer);
    reconnectTimer = null;
  }

  latestSnapshot = null;
  reconnectDelayMs = 1000;
  chatEventState.clear();

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

    dispatchRealtimeEvent(payload);
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

function dispatchRealtimeEvent(event: AppRealtimeEvent): void {
  if (isOrderedChatEvent(event)) {
    dispatchOrderedEvent(event, chatEventState, event.payload.session_id ?? event.payload.assistant_message_id);
    return;
  }

  listeners.forEach((listener) => listener(event));
}

function dispatchOrderedEvent(
  event: AppRealtimeEvent,
  stateStore: Map<
    string,
    {
      lastProcessedSequence: number;
      pendingEvents: Map<number, AppRealtimeEvent>;
    }
  >,
  sessionId: string,
): void {
  const sequence = (event as { payload: { sequence?: number } }).payload.sequence;

  if (sequence == null) {
    listeners.forEach((listener) => listener(event));
    return;
  }

  let state = stateStore.get(sessionId);
  if (!state) {
    state = {
      lastProcessedSequence: Math.max(0, sequence - 1),
      pendingEvents: new Map<number, AppRealtimeEvent>(),
    };
    stateStore.set(sessionId, state);
  }

  if (sequence <= state.lastProcessedSequence || state.pendingEvents.has(sequence)) {
    return;
  }

  state.pendingEvents.set(sequence, event);

  while (true) {
    const nextSequence = state.lastProcessedSequence + 1;
    const nextEvent = state.pendingEvents.get(nextSequence);
    if (!nextEvent) {
      break;
    }

    state.pendingEvents.delete(nextSequence);
    state.lastProcessedSequence = nextSequence;
    listeners.forEach((listener) => listener(nextEvent));
  }
}

function isOrderedChatEvent(
  event: AppRealtimeEvent,
): event is
  | { type: "chat_started"; payload: AppChatStartedPayload }
  | { type: "chat_delta"; payload: AppChatDeltaPayload }
  | { type: "chat_completed"; payload: AppChatCompletedPayload }
  | { type: "chat_failed"; payload: AppChatFailedPayload } {
  return (
    event.type === "chat_started" ||
    event.type === "chat_delta" ||
    event.type === "chat_completed" ||
    event.type === "chat_failed"
  );
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
