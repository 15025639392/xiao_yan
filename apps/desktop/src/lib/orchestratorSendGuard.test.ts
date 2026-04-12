import { describe, expect, test } from "vitest";

import {
  createOrchestratorSendGuardState,
  getOrchestratorSendBlockReason,
  markOrchestratorSendFinish,
  markOrchestratorSendStart,
  shouldBlockOrchestratorSend,
} from "./orchestratorSendGuard";

describe("orchestrator send guard", () => {
  test("blocks duplicate command while same command is inflight", () => {
    const state = createOrchestratorSendGuardState();
    markOrchestratorSendStart(state, "session-1", "继续推进", 1000);

    expect(shouldBlockOrchestratorSend(state, "session-1", "继续推进", 1001)).toBe(true);
    expect(getOrchestratorSendBlockReason(state, "session-1", "继续推进", 1001)).toBe("duplicate_inflight");
    markOrchestratorSendFinish(state, "session-1", "继续推进");
  });

  test("blocks same command within cooldown even after inflight finished", () => {
    const state = createOrchestratorSendGuardState();
    markOrchestratorSendStart(state, "session-1", "继续推进", 1000);
    markOrchestratorSendFinish(state, "session-1", "继续推进");

    expect(shouldBlockOrchestratorSend(state, "session-1", "继续推进", 1500)).toBe(true);
    expect(getOrchestratorSendBlockReason(state, "session-1", "继续推进", 1500)).toBe("duplicate_cooldown");
    expect(shouldBlockOrchestratorSend(state, "session-1", "继续推进", 2300)).toBe(false);
    expect(getOrchestratorSendBlockReason(state, "session-1", "继续推进", 2300)).toBeNull();
  });

  test("does not block different commands in the same session", () => {
    const state = createOrchestratorSendGuardState();
    markOrchestratorSendStart(state, "session-1", "继续推进", 1000);

    expect(shouldBlockOrchestratorSend(state, "session-1", "先解释当前推进到哪一步", 1001)).toBe(false);
  });

  test("does not cross-block different sessions", () => {
    const state = createOrchestratorSendGuardState();
    markOrchestratorSendStart(state, "session-1", "继续推进", 1000);

    expect(shouldBlockOrchestratorSend(state, "session-2", "继续推进", 1001)).toBe(false);
  });

  test("returns invalid payload for empty session or content", () => {
    const state = createOrchestratorSendGuardState();
    expect(getOrchestratorSendBlockReason(state, "", "继续推进", 1000)).toBe("invalid_payload");
    expect(getOrchestratorSendBlockReason(state, "session-1", "   ", 1000)).toBe("invalid_payload");
  });
});
