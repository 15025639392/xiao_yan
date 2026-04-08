import { useEffect, useRef, useState } from "react";
import { invoke } from "@tauri-apps/api/core";

import { ChatPanel } from "./components/ChatPanel";
import type { ChatEntry } from "./components/ChatPanel";
import { PersonaPanel } from "./components/PersonaPanel";
import { ToolPanel } from "./components/ToolPanel";
import type { BeingState, Goal, InnerWorldState, PersonaProfile } from "./lib/api";
import {
  chat,
  fetchGoals,
  fetchAutobio,
  fetchMessages,
  fetchState,
  fetchWorld,
  resumeChat,
  sleep,
  updateGoalStatus,
  updatePersonaFeatures,
  wake,
} from "./lib/api";
import { subscribeAppRealtime } from "./lib/realtime";
import { startCapabilityWorker } from "./lib/capabilities/worker";
import {
  appendAssistantDelta,
  finalizeAssistantMessage,
  markAssistantMessageFailed,
  markAssistantMessageStreaming,
  mergeMessages,
  upsertAssistantMessage,
} from "./lib/chatMessages";
import { OverviewPanel } from "./pages/OverviewPage";
import { MemoryPage } from "./pages/MemoryPage";
import { HistoryPage } from "./pages/HistoryPage";
import { CapabilitiesPage } from "./pages/CapabilitiesPage";

type AppRoute = "overview" | "chat" | "persona" | "memory" | "history" | "tools" | "capabilities";

const initialState: BeingState = {
  mode: "sleeping",
  focus_mode: "sleeping",
  current_thought: null,
  active_goal_ids: [],
  today_plan: null,
  last_action: null,
  self_programming_job: null,
};

export default function App() {
  const [route, setRoute] = useState<AppRoute>(() => resolveRoute(window.location.hash));
  const [state, setState] = useState<BeingState>(initialState);
  const [world, setWorld] = useState<InnerWorldState | null>(null);
  const [autobioEntries, setAutobioEntries] = useState<string[]>([]);
  const [messages, setMessages] = useState<ChatEntry[]>([]);
  const [goals, setGoals] = useState<Goal[]>([]);
  const [persona, setPersona] = useState<PersonaProfile | null>(null);
  const [draft, setDraft] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState("");
  const [theme, setTheme] = useState<"dark" | "light">(() => loadThemePreference());
  const [showBrandMenu, setShowBrandMenu] = useState(false);
  const [showAbout, setShowAbout] = useState(false);
  const [petVisible, setPetVisible] = useState(false);
  const pendingRequestMessageRef = useRef<string | null>(null);
  const focusGoalTitle = resolveFocusGoalTitle(state, goals);
  const assistantName = persona?.name?.trim() || "小晏";
  const assistantIdentity = persona?.identity?.trim() || "AI Agent Desktop";

  useEffect(() => {
    let cancelled = false;

    async function syncRuntime() {
      try {
        const [nextState, nextMessages, nextGoals, nextWorld, nextAutobio] = await Promise.all([
          fetchState(),
          fetchMessages(),
          fetchGoals(),
          fetchWorld(),
          fetchAutobio(),
        ]);

        if (cancelled) {
          return;
        }

        setState(nextState);
        setMessages((current) => mergeMessages(current, nextMessages.messages));
        setGoals(nextGoals.goals);
        setWorld(nextWorld);
        setAutobioEntries(nextAutobio.entries);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "同步失败");
        }
      }
    }

    void syncRuntime();
    const unsubscribe = subscribeAppRealtime((event) => {
      if (cancelled) {
        return;
      }

      if (event.type === "chat_started") {
        const requestMessage = pendingRequestMessageRef.current ?? undefined;
        setMessages((current) =>
          upsertAssistantMessage(
            current,
            event.payload.assistant_message_id,
            "",
            "streaming",
            requestMessage,
            event.payload.sequence,
          )
        );
        pendingRequestMessageRef.current = null;
        setError("");
        return;
      }

      if (event.type === "chat_delta") {
        setMessages((current) => {
          const updated = appendAssistantDelta(
            current,
            event.payload.assistant_message_id,
            event.payload.delta,
            event.payload.sequence,
          );
          return updated;
        });
        setError("");
        return;
      }

      if (event.type === "chat_completed") {
        setMessages((current) => {
          const updated = finalizeAssistantMessage(
            current,
            event.payload.assistant_message_id,
            event.payload.content,
            event.payload.sequence,
          );
          return updated;
        });
        setError("");
        return;
      }

      if (event.type === "chat_failed") {
        setMessages((current) =>
          markAssistantMessageFailed(current, event.payload.assistant_message_id, event.payload.sequence)
        );
        setError(event.payload.error);
        return;
      }

      const runtimePayload =
        event.type === "snapshot" ? event.payload.runtime : event.type === "runtime_updated" ? event.payload : null;
      if (!runtimePayload) {
        return;
      }

      setState(runtimePayload.state);
      setMessages((current) => mergeMessages(current, runtimePayload.messages));
      setGoals(runtimePayload.goals);
      setWorld(runtimePayload.world);
      setAutobioEntries(runtimePayload.autobio);
      setError("");
    });

    const unsubscribePersona = subscribeAppRealtime((event) => {
      if (cancelled) {
        return;
      }

      const personaPayload =
        event.type === "snapshot" ? event.payload.persona : event.type === "persona_updated" ? event.payload : null;
      if (!personaPayload) {
        return;
      }

      setPersona(personaPayload.profile);
    });

    return () => {
      cancelled = true;
      unsubscribe();
      unsubscribePersona();
    };
  }, []);

  // 主题切换：更新 DOM 和 localStorage
  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("theme", theme);
  }, [theme]);

  useEffect(() => {
    const syncRoute = () => {
      setRoute(resolveRoute(window.location.hash));
    };

    if (!window.location.hash) {
      window.location.hash = routeToHash("overview");
    } else {
      syncRoute();
    }

    window.addEventListener("hashchange", syncRoute);
    return () => {
      window.removeEventListener("hashchange", syncRoute);
    };
  }, []);

  // Pet visibility probe (Tauri). Best-effort: feature might be unavailable on some platforms.
  useEffect(() => {
    invoke("pet_is_visible")
      .then((result: any) => {
        if (result && typeof result.visible === "boolean") {
          setPetVisible(result.visible);
        }
      })
      .catch(() => {
        // ignore
      });
  }, []);

  // Keep pet window in sync with persona feature toggle.
  useEffect(() => {
    const enabled = persona?.features?.avatar_enabled ?? false;
    invoke(enabled ? "pet_show" : "pet_close")
      .then((result: any) => {
        if (result && typeof result.visible === "boolean") {
          setPetVisible(result.visible);
        } else {
          setPetVisible(enabled);
        }
      })
      .catch(() => {
        // ignore
      });
  }, [persona?.features?.avatar_enabled]);

  // Desktop capability worker: pull pending capability requests from core and execute locally.
  useEffect(() => {
    const stop = startCapabilityWorker();
    return () => {
      stop();
    };
  }, []);

  async function handleWake() {
    try {
      setError("");
      setState(await wake());
    } catch (err) {
      setError(err instanceof Error ? err.message : "唤醒失败");
    }
  }

  async function handleSleep() {
    try {
      setError("");
      setState(await sleep());
    } catch (err) {
      setError(err instanceof Error ? err.message : "休眠失败");
    }
  }

  // ===== Pet (Desktop Pet) =====
  async function handlePetEnabledChange(enabled: boolean) {
    try {
      setError("");
      const updated = await updatePersonaFeatures({ avatar_enabled: enabled });
      setPersona(updated.profile);
      // Window lifecycle is centralized in the persona-sync effect
      // to avoid duplicate concurrent `pet_show` / `pet_close` calls.
      setPetVisible(enabled);
    } catch (err) {
      const message =
        err instanceof Error
          ? err.message
          : typeof err === "string"
            ? err
            : err
              ? JSON.stringify(err)
              : "";
      setError(message || "宠物操作失败");
    }
  }

  async function handleSend() {
    const content = draft.trim();
    if (!content) {
      return;
    }

    const userMessage: ChatEntry = {
      id: `user-${Date.now()}`,
      role: "user",
      content,
    };

    setError("");
    setDraft("");
    setMessages((current) => [...current, userMessage]);
    pendingRequestMessageRef.current = content;
    setIsSending(true);

    try {
      const result = await chat(content);
    } catch (err) {
      setError(err instanceof Error ? err.message : "发送失败");
    } finally {
      setIsSending(false);
    }
  }

  async function handleResume(message: ChatEntry) {
    if (message.role !== "assistant" || !message.requestMessage) {
      return;
    }

    setError("");
    setIsSending(true);
    setMessages((current) => markAssistantMessageStreaming(current, message.id));

    try {
      await resumeChat({
        message: message.requestMessage,
        assistant_message_id: message.id,
        partial_content: message.content,
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "继续生成失败");
    } finally {
      setIsSending(false);
    }
  }

  async function handleUpdateGoalStatus(goalId: string, status: Goal["status"]) {
    try {
      setError("");
      const updatedGoal = await updateGoalStatus(goalId, status);
      const refreshedState = await fetchState();

      setGoals((current) =>
        current.map((goal) => (goal.id === updatedGoal.id ? updatedGoal : goal))
      );
      setState(refreshedState);
    } catch (err) {
      setError(err instanceof Error ? err.message : "目标状态更新失败");
    }
  }

  async function handleRollback(jobId: string) {
    try {
      setError("");
      // 回滚后刷新状态
      const refreshedState = await fetchState();
      setState(refreshedState);
    } catch (err) {
      setError(err instanceof Error ? err.message : "回滚失败");
    }
  }

  async function handleApprovalDecision(jobId: string, approved: boolean) {
    try {
      setError("");
      // 审批操作已由 ApprovalPanel 内部调用 API 完成，这里只做状态刷新
      const refreshedState = await fetchState();
      setState(refreshedState);
    } catch (err) {
      setError(err instanceof Error ? err.message : "审批状态更新失败");
    }
  }

  function handleNavigate(nextRoute: AppRoute) {
    const nextHash = routeToHash(nextRoute);
    if (window.location.hash !== nextHash) {
      window.location.hash = nextHash;
      return;
    }

    setRoute(nextRoute);
  }

  const isAwake = state.mode === "awake";

  return (
    <div className="app-layout">
      {/* Left Sidebar - WorkBuddy Style */}
      <aside className="app-sidebar">
        <div className="app-sidebar__header">
          <div className="app-sidebar__brand-dropdown">
            <button
              type="button"
              className="app-sidebar__brand"
              onClick={() => setShowBrandMenu(!showBrandMenu)}
            >
              <span className="app-sidebar__logo">🤖</span>
              <span className="app-sidebar__title">{assistantName}</span>
              <svg
                className={`app-sidebar__brand-chevron ${showBrandMenu ? 'app-sidebar__brand-chevron--open' : ''}`}
                width="14"
                height="14"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
              >
                <polyline points="6 9 12 15 18 9" />
              </svg>
            </button>
            {showBrandMenu && (
              <div className="app-sidebar__brand-menu">
                <button
                  type="button"
                  className="app-sidebar__brand-menu-item"
                  onClick={() => {
                    setTheme(theme === "dark" ? "light" : "dark");
                    setShowBrandMenu(false);
                  }}
                >
                  <span>{theme === "dark" ? "☀️" : "🌙"}</span>
                  <span>切换{theme === "dark" ? "浅色" : "深色"}主题</span>
                </button>
                <button
                  type="button"
                  className="app-sidebar__brand-menu-item"
                  onClick={() => {
                    setShowAbout(true);
                    setShowBrandMenu(false);
                  }}
                >
                  <span>ℹ️</span>
                  <span>关于</span>
                </button>
              </div>
            )}
          </div>
          <div className={`app-sidebar__status-dot app-sidebar__status-dot--${state.mode}`} />
        </div>

        <nav className="app-sidebar__nav" aria-label="主导航">
          <button
            className={`app-sidebar__nav-item ${route === "overview" ? "app-sidebar__nav-item--active" : ""}`}
            onClick={() => handleNavigate("overview")}
            type="button"
          >
            <svg className="app-sidebar__nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <rect x="3" y="3" width="7" height="7" rx="1" />
              <rect x="14" y="3" width="7" height="7" rx="1" />
              <rect x="14" y="14" width="7" height="7" rx="1" />
              <rect x="3" y="14" width="7" height="7" rx="1" />
            </svg>
            <span>总览</span>
          </button>
          <button
            className={`app-sidebar__nav-item ${route === "chat" ? "app-sidebar__nav-item--active" : ""}`}
            onClick={() => handleNavigate("chat")}
            type="button"
          >
            <svg className="app-sidebar__nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
            </svg>
            <span>对话</span>
          </button>
          <button
            className={`app-sidebar__nav-item ${route === "persona" ? "app-sidebar__nav-item--active" : ""}`}
            onClick={() => handleNavigate("persona")}
            type="button"
          >
            <svg className="app-sidebar__nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
              <circle cx="12" cy="7" r="4"/>
            </svg>
            <span>人格</span>
          </button>
          <button
            className={`app-sidebar__nav-item ${route === "memory" ? "app-sidebar__nav-item--active" : ""}`}
            onClick={() => handleNavigate("memory")}
            type="button"
          >
            <svg className="app-sidebar__nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M12 2a10 10 0 1 0 10 10H12V2z"/>
              <path d="M12 2a10 10 0 0 1 10 10"/>
              <path d="M12 12L2.5 12"/>
            </svg>
            <span>记忆</span>
          </button>
          <button
            className={`app-sidebar__nav-item ${route === "tools" ? "app-sidebar__nav-item--active" : ""}`}
            onClick={() => handleNavigate("tools")}
            type="button"
          >
            <svg className="app-sidebar__nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M14.7 6.3a1 1 0 0 0 0-1.4l1.83-2a1 1 0 0 0-1.42-1.4L13.28 5.17a4 4 0 1 0-5.66 5.66l-8.49 8.49a1 1 0 0 0-1.41 0"/>
              <path d="M16 21v-6a1 1 0 0 1 1-1h6"/>
            </svg>
            <span>工具箱</span>
          </button>
          <button
            className={`app-sidebar__nav-item ${route === "capabilities" ? "app-sidebar__nav-item--active" : ""}`}
            onClick={() => handleNavigate("capabilities")}
            type="button"
          >
            <svg className="app-sidebar__nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <rect x="4" y="4" width="7" height="7" rx="1" />
              <rect x="13" y="4" width="7" height="7" rx="1" />
              <rect x="4" y="13" width="7" height="7" rx="1" />
              <path d="M13 16h7M16.5 13v7" />
            </svg>
            <span>能力中枢</span>
          </button>
        </nav>

        <div className="app-sidebar__section">
          <div className="app-sidebar__section-title">控制</div>
          <div className="app-sidebar__actions">
            <button
              className="app-sidebar__action-btn app-sidebar__action-btn--primary"
              onClick={handleWake}
              type="button"
              disabled={isAwake}
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83" />
              </svg>
              唤醒
            </button>
            <button
              className="app-sidebar__action-btn"
              onClick={handleSleep}
              type="button"
              disabled={!isAwake}
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
              </svg>
              休眠
            </button>
          </div>
        </div>

        <div className="app-sidebar__footer">
          <div className="app-sidebar__status">
            <span className={`app-sidebar__status-indicator app-sidebar__status-indicator--${state.mode}`} />
            <span className="app-sidebar__status-text">{isAwake ? "运行中" : "休眠中"}</span>
          </div>
        </div>
      </aside>

      {/* Main Content */}
      <main className="app-main">
        {/* Error Banner */}
        {error ? (
          <div className="error-banner">
            <strong>错误：</strong>
            {error}
          </div>
        ) : null}

        {route === "chat" ? (
          <ChatPanel
            assistantName={assistantName}
            draft={draft}
            focusGoalTitle={focusGoalTitle}
            focusModeLabel={renderFocusModeLabel(state.focus_mode)}
            isSending={isSending}
            messages={messages}
            modeLabel={isAwake ? "运行中" : "休眠中"}
            todayPlan={state.today_plan}
            activeGoals={goals.filter(g => g.status === "active")}
            onDraftChange={setDraft}
            onSend={handleSend}
            onResume={handleResume}
            onCompleteGoal={(goalId) => handleUpdateGoalStatus(goalId, "completed")}
          />
        ) : route === "persona" ? (
          <PersonaPanel
            assistantName={assistantName}
            petEnabled={persona?.features?.avatar_enabled ?? false}
            petVisible={petVisible}
            onSetPetEnabled={handlePetEnabledChange}
          />
        ) : route === "memory" ? (
          <MemoryPage assistantName={assistantName} />
        ) : route === "history" ? (
          <HistoryPage onSelectRollback={handleRollback} />
        ) : route === "tools" ? (
          <ToolPanel />
        ) : route === "capabilities" ? (
          <CapabilitiesPage />
        ) : (
          <OverviewPanel
            focusGoalTitle={focusGoalTitle}
            goals={goals}
            latestActionLabel={state.last_action ? `${state.last_action.command} -> ${state.last_action.output}` : null}
            mode={state.mode}
            onUpdateGoalStatus={handleUpdateGoalStatus}
            state={state}
            world={world}
            autobioEntries={autobioEntries}
            onRollback={handleRollback}
            onApprovalDecision={handleApprovalDecision}
          />
        )}

        {/* 关于弹窗 */}
        {showAbout && (
          <div className="modal-overlay" onClick={() => setShowAbout(false)}>
            <div className="modal modal--sm" onClick={(e) => e.stopPropagation()}>
              <div className="modal__header">
                <h3 className="modal__title">关于 {assistantName}</h3>
                <button
                  type="button"
                  className="modal__close"
                  onClick={() => setShowAbout(false)}
                >
                  ×
                </button>
              </div>
              <div className="modal__body">
                <div className="about-content">
                  <div className="about-logo">🤖</div>
                  <h4 className="about-name">{assistantName}</h4>
                  <p className="about-desc">{assistantIdentity}</p>
                  <div className="about-meta">
                    <div className="about-meta__item">
                      <span className="about-meta__label">版本</span>
                      <span className="about-meta__value">v0.1.0</span>
                    </div>
                    <div className="about-meta__item">
                      <span className="about-meta__label">人格系统</span>
                      <span className="about-meta__value">情绪驱动</span>
                    </div>
                    <div className="about-meta__item">
                      <span className="about-meta__label">记忆系统</span>
                      <span className="about-meta__value">结构化记忆</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}

function resolveRoute(hash: string): AppRoute {
  if (hash === "#/chat") return "chat";
  if (hash === "#/persona") return "persona";
  if (hash === "#/memory") return "memory";
  if (hash === "#/history") return "history";
  if (hash === "#/tools") return "tools";
  if (hash === "#/capabilities") return "capabilities";
  return "overview";
}

function routeToHash(route: AppRoute): string {
  if (route === "chat") return "#/chat";
  if (route === "persona") return "#/persona";
  if (route === "memory") return "#/memory";
  if (route === "history") return "#/history";
  if (route === "tools") return "#/tools";
  if (route === "capabilities") return "#/capabilities";
  return "#/";
}

function resolveFocusGoalTitle(state: BeingState, goals: Goal[]): string | null {
  if (state.active_goal_ids.length > 0) {
    const currentGoal = goals.find((goal) => goal.id === state.active_goal_ids[0]);
    if (currentGoal) {
      return currentGoal.title;
    }
  }

  return state.today_plan?.goal_title ?? null;
}

function renderFocusModeLabel(focusMode: BeingState["focus_mode"]): string {
  if (focusMode === "morning_plan") {
    return "晨间计划";
  }
  if (focusMode === "autonomy") {
    return "常规自主";
  }
  if (focusMode === "self_programming") {
    return "自我编程";
  }
  return "休眠";
}

function loadThemePreference(): "dark" | "light" {
  if (typeof window === "undefined") {
    return "dark";
  }
  const saved = localStorage.getItem("theme");
  if (saved === "light" || saved === "dark") {
    return saved;
  }
  // 检测系统偏好
  if (window.matchMedia && window.matchMedia("(prefers-color-scheme: light)").matches) {
    return "light";
  }
  return "dark";
}
