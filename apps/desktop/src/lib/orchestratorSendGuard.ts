export type OrchestratorSendGuardState = {
  inflightBySession: Map<string, Set<string>>;
  lastSentBySession: Map<string, { content: string; sentAtMs: number }>;
};

export type OrchestratorSendBlockReason =
  | "invalid_payload"
  | "duplicate_inflight"
  | "duplicate_cooldown";

const DEFAULT_REPEAT_COOLDOWN_MS = 1200;

export function createOrchestratorSendGuardState(): OrchestratorSendGuardState {
  return {
    inflightBySession: new Map(),
    lastSentBySession: new Map(),
  };
}

export function shouldBlockOrchestratorSend(
  state: OrchestratorSendGuardState,
  sessionId: string,
  content: string,
  nowMs: number,
  repeatCooldownMs = DEFAULT_REPEAT_COOLDOWN_MS,
): boolean {
  return (
    getOrchestratorSendBlockReason(state, sessionId, content, nowMs, repeatCooldownMs)
    !== null
  );
}

export function getOrchestratorSendBlockReason(
  state: OrchestratorSendGuardState,
  sessionId: string,
  content: string,
  nowMs: number,
  repeatCooldownMs = DEFAULT_REPEAT_COOLDOWN_MS,
): OrchestratorSendBlockReason | null {
  const normalized = content.trim();
  if (!sessionId || !normalized) {
    return "invalid_payload";
  }

  const inflight = state.inflightBySession.get(sessionId);
  if (inflight?.has(normalized)) {
    return "duplicate_inflight";
  }

  const lastSent = state.lastSentBySession.get(sessionId);
  if (
    lastSent != null
    && lastSent.content === normalized
    && nowMs - lastSent.sentAtMs < repeatCooldownMs
  ) {
    return "duplicate_cooldown";
  }

  return null;
}

export function markOrchestratorSendStart(
  state: OrchestratorSendGuardState,
  sessionId: string,
  content: string,
  nowMs: number,
): void {
  const normalized = content.trim();
  if (!sessionId || !normalized) {
    return;
  }

  const inflight = state.inflightBySession.get(sessionId) ?? new Set<string>();
  inflight.add(normalized);
  state.inflightBySession.set(sessionId, inflight);
  state.lastSentBySession.set(sessionId, {
    content: normalized,
    sentAtMs: nowMs,
  });
}

export function markOrchestratorSendFinish(
  state: OrchestratorSendGuardState,
  sessionId: string,
  content: string,
): void {
  const normalized = content.trim();
  if (!sessionId || !normalized) {
    return;
  }

  const inflight = state.inflightBySession.get(sessionId);
  if (!inflight) {
    return;
  }

  inflight.delete(normalized);
  if (inflight.size === 0) {
    state.inflightBySession.delete(sessionId);
  }
}
