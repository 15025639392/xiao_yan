import { describe, expect, test } from "vitest";

import {
  createInitialOrchestratorConsoleState,
  orchestratorConsoleReducer,
  resolveActiveSessionId,
  resolveActiveTabDraft,
  resolveActiveWorkbenchTab,
} from "./orchestratorConsoleState";

describe("orchestratorConsoleState", () => {
  test("starts with one blank tab", () => {
    const state = createInitialOrchestratorConsoleState();
    expect(state.tabs).toHaveLength(1);
    expect(state.tabs[0]?.type).toBe("blank");
    expect(resolveActiveSessionId(state)).toBeNull();
  });

  test("can create blank tab with preset draft", () => {
    const initial = createInitialOrchestratorConsoleState();
    const next = orchestratorConsoleReducer(initial, {
      type: "add_blank_tab",
      draft: "进入主控，处理当前项目",
    });

    expect(next.tabs).toHaveLength(2);
    expect(resolveActiveTabDraft(next)).toBe("进入主控，处理当前项目");
    expect(resolveActiveWorkbenchTab(next)?.type).toBe("blank");
  });

  test("converts blank tab to session tab after first command", () => {
    const initial = createInitialOrchestratorConsoleState();
    const blankId = initial.activeTabId;
    const next = orchestratorConsoleReducer(initial, {
      type: "convert_blank_to_session",
      tabId: blankId,
      sessionId: "session-1",
    });

    expect(next.tabs).toHaveLength(1);
    expect(next.tabs[0]).toEqual({
      tab_id: blankId,
      type: "session",
      session_id: "session-1",
    });
    expect(resolveActiveSessionId(next)).toBe("session-1");
  });

  test("removes deleted session tabs and keeps at least one blank tab", () => {
    const initial = createInitialOrchestratorConsoleState();
    const blankId = initial.activeTabId;
    const withSession = orchestratorConsoleReducer(initial, {
      type: "convert_blank_to_session",
      tabId: blankId,
      sessionId: "session-1",
    });

    const next = orchestratorConsoleReducer(withSession, {
      type: "remove_session_tabs",
      sessionId: "session-1",
    });
    expect(next.tabs).toHaveLength(1);
    expect(next.tabs[0]?.type).toBe("blank");
    expect(resolveActiveSessionId(next)).toBeNull();
  });

  test("sync sessions auto-focuses preferred session when active blank tab has no draft", () => {
    const initial = createInitialOrchestratorConsoleState();
    const next = orchestratorConsoleReducer(initial, {
      type: "sync_sessions",
      sessionIds: ["session-1"],
      preferredSessionId: "session-1",
    });

    expect(resolveActiveSessionId(next)).toBe("session-1");
  });

  test("sync sessions keeps active blank tab when it has draft text", () => {
    const initial = createInitialOrchestratorConsoleState();
    const withDraft = orchestratorConsoleReducer(initial, {
      type: "set_draft",
      tabId: initial.activeTabId,
      draft: "先草拟一条主控指令",
    });
    const next = orchestratorConsoleReducer(withDraft, {
      type: "sync_sessions",
      sessionIds: ["session-1"],
      preferredSessionId: "session-1",
    });

    expect(resolveActiveSessionId(next)).toBeNull();
    expect(resolveActiveWorkbenchTab(next)?.type).toBe("blank");
  });
});
