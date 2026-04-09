import { BASE_URL } from "./api";
import type {
  BeingState,
  ChatHistoryMessage,
  EmotionState,
  Goal,
  GoalAdmissionCandidateSnapshot,
  GoalAdmissionStats,
  InnerWorldState,
  MemoryEntryDisplay,
  MemorySummary,
  OrchestratorPlan,
  OrchestratorMessage,
  OrchestratorSession,
  OrchestratorTask,
  OrchestratorVerification,
  PersonaProfile,
  RelationshipSummary,
} from "./api";

export type AppRuntimeRealtimePayload = {
  state: BeingState;
  messages: ChatHistoryMessage[];
  goals: Goal[];
  goal_admission_stats?: GoalAdmissionStats | null;
  goal_admission_candidates?: GoalAdmissionCandidateSnapshot | null;
  world: InnerWorldState | null;
  autobio: string[];
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
  session_id?: string;
  sequence?: number;
  timestamp_ms?: number;
};

export type AppChatDeltaPayload = {
  assistant_message_id: string;
  delta: string;
  session_id?: string;
  sequence?: number;
  timestamp_ms?: number;
};

export type AppChatCompletedPayload = {
  assistant_message_id: string;
  response_id: string | null;
  content: string;
  session_id?: string;
  sequence?: number;
  timestamp_ms?: number;
};

export type AppChatFailedPayload = {
  assistant_message_id: string;
  error: string;
  session_id?: string;
  sequence?: number;
  timestamp_ms?: number;
};

export type AppOrchestratorTaskUpdatedPayload = {
  session_id: string;
  task: OrchestratorTask;
};

export type AppOrchestratorPlanPendingPayload = {
  session_id: string;
  plan: OrchestratorPlan;
};

export type AppOrchestratorVerificationCompletedPayload = {
  session_id: string;
  verification: OrchestratorVerification;
  status: OrchestratorSession["status"];
};

export type AppOrchestratorMessageStartedPayload = {
  session_id: string;
  assistant_message_id: string;
  response_id: string | null;
  sequence?: number;
  timestamp_ms?: number;
};

export type AppOrchestratorMessageDeltaPayload = {
  session_id: string;
  assistant_message_id: string;
  delta: string;
  sequence?: number;
  timestamp_ms?: number;
};

export type AppOrchestratorMessageCompletedPayload = {
  session_id: string;
  assistant_message_id: string;
  response_id: string | null;
  content: string;
  blocks: OrchestratorMessage["blocks"];
  sequence?: number;
  timestamp_ms?: number;
};

export type AppOrchestratorMessageFailedPayload = {
  session_id: string;
  assistant_message_id: string;
  error: string;
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
  | { type: "chat_failed"; payload: AppChatFailedPayload }
  | { type: "orchestrator_session_updated"; payload: OrchestratorSession }
  | { type: "orchestrator_task_updated"; payload: AppOrchestratorTaskUpdatedPayload }
  | { type: "orchestrator_plan_pending_approval"; payload: AppOrchestratorPlanPendingPayload }
  | { type: "orchestrator_verification_completed"; payload: AppOrchestratorVerificationCompletedPayload }
  | { type: "orchestrator_message_started"; payload: AppOrchestratorMessageStartedPayload }
  | { type: "orchestrator_message_delta"; payload: AppOrchestratorMessageDeltaPayload }
  | { type: "orchestrator_message_completed"; payload: AppOrchestratorMessageCompletedPayload }
  | { type: "orchestrator_message_failed"; payload: AppOrchestratorMessageFailedPayload }
  | { type: "orchestrator_message_appended"; payload: OrchestratorMessage };

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
const orchestratorEventState = new Map<
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
  orchestratorEventState.clear();

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

  if (isOrderedOrchestratorEvent(event)) {
    dispatchOrderedEvent(event, orchestratorEventState, `orchestrator:${event.payload.session_id}`);
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

function isOrderedOrchestratorEvent(
  event: AppRealtimeEvent,
): event is
  | { type: "orchestrator_message_started"; payload: AppOrchestratorMessageStartedPayload }
  | { type: "orchestrator_message_delta"; payload: AppOrchestratorMessageDeltaPayload }
  | { type: "orchestrator_message_completed"; payload: AppOrchestratorMessageCompletedPayload }
  | { type: "orchestrator_message_failed"; payload: AppOrchestratorMessageFailedPayload } {
  return (
    event.type === "orchestrator_message_started" ||
    event.type === "orchestrator_message_delta" ||
    event.type === "orchestrator_message_completed" ||
    event.type === "orchestrator_message_failed"
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
