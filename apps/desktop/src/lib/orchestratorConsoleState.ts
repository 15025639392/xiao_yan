import type { WorkbenchTab } from "./api";

export type OrchestratorConsoleState = {
  tabs: WorkbenchTab[];
  activeTabId: string;
  draftsByTab: Record<string, string>;
};

export type OrchestratorConsoleAction =
  | {
      type: "sync_sessions";
      sessionIds: string[];
      preferredSessionId?: string | null;
    }
  | {
      type: "add_blank_tab";
      draft?: string;
      activate?: boolean;
    }
  | {
      type: "activate_tab";
      tabId: string;
    }
  | {
      type: "close_tab";
      tabId: string;
    }
  | {
      type: "set_draft";
      tabId: string;
      draft: string;
    }
  | {
      type: "ensure_session_tab";
      sessionId: string;
      activate?: boolean;
    }
  | {
      type: "convert_blank_to_session";
      tabId: string;
      sessionId: string;
      activate?: boolean;
    }
  | {
      type: "remove_session_tabs";
      sessionId: string;
    };

let blankTabCounter = 0;

function createBlankTab(): WorkbenchTab {
  blankTabCounter += 1;
  return {
    tab_id: `blank-${Date.now()}-${blankTabCounter}`,
    type: "blank",
  };
}

function ensureAtLeastOneTab(tabs: WorkbenchTab[]): WorkbenchTab[] {
  if (tabs.length > 0) {
    return tabs;
  }
  return [createBlankTab()];
}

function nextActiveTabId(
  tabs: WorkbenchTab[],
  currentActiveTabId: string,
  fallbackPreferredTabId?: string | null,
): string {
  if (tabs.some((tab) => tab.tab_id === currentActiveTabId)) {
    return currentActiveTabId;
  }
  if (fallbackPreferredTabId && tabs.some((tab) => tab.tab_id === fallbackPreferredTabId)) {
    return fallbackPreferredTabId;
  }
  return tabs[0]?.tab_id ?? createBlankTab().tab_id;
}

function cleanupDrafts(draftsByTab: Record<string, string>, tabs: WorkbenchTab[]): Record<string, string> {
  const allowed = new Set(tabs.map((tab) => tab.tab_id));
  const next: Record<string, string> = {};
  for (const [key, value] of Object.entries(draftsByTab)) {
    if (allowed.has(key)) {
      next[key] = value;
    }
  }
  return next;
}

export function createInitialOrchestratorConsoleState(): OrchestratorConsoleState {
  const blank = createBlankTab();
  return {
    tabs: [blank],
    activeTabId: blank.tab_id,
    draftsByTab: {},
  };
}

export function orchestratorConsoleReducer(
  state: OrchestratorConsoleState,
  action: OrchestratorConsoleAction,
): OrchestratorConsoleState {
  if (action.type === "sync_sessions") {
    const sessionIdSet = new Set(action.sessionIds.filter((item) => item.trim().length > 0));
    let tabs = state.tabs.filter((tab) => tab.type === "blank" || sessionIdSet.has(tab.session_id));
    const preferredSessionId = action.preferredSessionId?.trim();
    let preferredTabId: string | null = null;
    if (preferredSessionId) {
      const hasPreferred = tabs.some((tab) => tab.type === "session" && tab.session_id === preferredSessionId);
      if (!hasPreferred) {
        tabs = [
          {
            tab_id: `session-${preferredSessionId}`,
            type: "session",
            session_id: preferredSessionId,
          },
          ...tabs,
        ];
      }
      preferredTabId =
        tabs.find((tab) => tab.type === "session" && tab.session_id === preferredSessionId)?.tab_id ?? null;
    }
    tabs = ensureAtLeastOneTab(tabs);
    let activeTabId = nextActiveTabId(tabs, state.activeTabId);
    if (preferredTabId) {
      const currentActive = state.tabs.find((tab) => tab.tab_id === state.activeTabId) ?? null;
      const activeDraft = state.draftsByTab[state.activeTabId] ?? "";
      const shouldAutoActivatePreferred =
        currentActive === null || (currentActive.type === "blank" && activeDraft.trim().length === 0);
      if (shouldAutoActivatePreferred) {
        activeTabId = preferredTabId;
      }
    }
    return {
      tabs,
      activeTabId,
      draftsByTab: cleanupDrafts(state.draftsByTab, tabs),
    };
  }

  if (action.type === "add_blank_tab") {
    const blank = createBlankTab();
    const tabs = [...state.tabs, blank];
    const draftsByTab = { ...state.draftsByTab };
    if (action.draft && action.draft.trim().length > 0) {
      draftsByTab[blank.tab_id] = action.draft;
    }
    return {
      tabs,
      activeTabId: action.activate === false ? state.activeTabId : blank.tab_id,
      draftsByTab,
    };
  }

  if (action.type === "activate_tab") {
    if (!state.tabs.some((tab) => tab.tab_id === action.tabId)) {
      return state;
    }
    return {
      ...state,
      activeTabId: action.tabId,
    };
  }

  if (action.type === "close_tab") {
    const index = state.tabs.findIndex((tab) => tab.tab_id === action.tabId);
    if (index < 0) {
      return state;
    }
    let tabs = state.tabs.filter((tab) => tab.tab_id !== action.tabId);
    tabs = ensureAtLeastOneTab(tabs);
    const fallbackTab = tabs[Math.min(index, tabs.length - 1)]?.tab_id ?? tabs[0].tab_id;
    const activeTabId =
      state.activeTabId === action.tabId ? fallbackTab : nextActiveTabId(tabs, state.activeTabId, fallbackTab);
    return {
      tabs,
      activeTabId,
      draftsByTab: cleanupDrafts(
        Object.fromEntries(Object.entries(state.draftsByTab).filter(([key]) => key !== action.tabId)),
        tabs,
      ),
    };
  }

  if (action.type === "set_draft") {
    if (!state.tabs.some((tab) => tab.tab_id === action.tabId)) {
      return state;
    }
    return {
      ...state,
      draftsByTab: {
        ...state.draftsByTab,
        [action.tabId]: action.draft,
      },
    };
  }

  if (action.type === "ensure_session_tab") {
    const normalizedSessionId = action.sessionId.trim();
    if (!normalizedSessionId) {
      return state;
    }
    const existing = state.tabs.find((tab) => tab.type === "session" && tab.session_id === normalizedSessionId);
    if (existing) {
      if (action.activate) {
        return {
          ...state,
          activeTabId: existing.tab_id,
        };
      }
      return state;
    }
    const tab: WorkbenchTab = {
      tab_id: `session-${normalizedSessionId}`,
      type: "session",
      session_id: normalizedSessionId,
    };
    return {
      tabs: [tab, ...state.tabs],
      activeTabId: action.activate ? tab.tab_id : state.activeTabId,
      draftsByTab: state.draftsByTab,
    };
  }

  if (action.type === "convert_blank_to_session") {
    const normalizedSessionId = action.sessionId.trim();
    if (!normalizedSessionId) {
      return state;
    }
    const existingSessionTab = state.tabs.find(
      (tab) => tab.type === "session" && tab.session_id === normalizedSessionId,
    );
    if (existingSessionTab) {
      const tabs = state.tabs.filter((tab) => tab.tab_id !== action.tabId);
      return {
        tabs: ensureAtLeastOneTab(tabs),
        activeTabId: action.activate === false ? state.activeTabId : existingSessionTab.tab_id,
        draftsByTab: cleanupDrafts(
          Object.fromEntries(Object.entries(state.draftsByTab).filter(([key]) => key !== action.tabId)),
          ensureAtLeastOneTab(tabs),
        ),
      };
    }
    const tabs = state.tabs.map((tab) =>
      tab.tab_id === action.tabId
        ? {
            tab_id: tab.tab_id,
            type: "session",
            session_id: normalizedSessionId,
          }
        : tab,
    );
    const nextTabs = ensureAtLeastOneTab(tabs);
    return {
      tabs: nextTabs,
      activeTabId: action.activate === false ? state.activeTabId : action.tabId,
      draftsByTab: cleanupDrafts(state.draftsByTab, nextTabs),
    };
  }

  if (action.type === "remove_session_tabs") {
    const tabs = ensureAtLeastOneTab(
      state.tabs.filter((tab) => !(tab.type === "session" && tab.session_id === action.sessionId)),
    );
    return {
      tabs,
      activeTabId: nextActiveTabId(tabs, state.activeTabId),
      draftsByTab: cleanupDrafts(state.draftsByTab, tabs),
    };
  }

  return state;
}

export function resolveActiveWorkbenchTab(state: OrchestratorConsoleState): WorkbenchTab | null {
  return state.tabs.find((tab) => tab.tab_id === state.activeTabId) ?? state.tabs[0] ?? null;
}

export function resolveActiveSessionId(state: OrchestratorConsoleState): string | null {
  const tab = resolveActiveWorkbenchTab(state);
  if (!tab || tab.type !== "session") {
    return null;
  }
  return tab.session_id;
}

export function resolveActiveTabDraft(state: OrchestratorConsoleState): string {
  return state.draftsByTab[state.activeTabId] ?? "";
}
