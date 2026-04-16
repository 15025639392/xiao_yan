import { useCallback, useEffect, useReducer, useRef, useState } from "react";
import { invoke } from "@tauri-apps/api/core";

import { ChatPanel } from "./components/ChatPanel";
import type { ChatEntry, ChatSendOptions } from "./components/ChatPanel";
import { PersonaPanel } from "./components/PersonaPanel";
import { ToolPanel } from "./components/ToolPanel";
import type {
  BeingState,
  ChatAttachment,
  ChatRequestBody,
  Goal,
  InnerWorldState,
  MacConsoleBootstrapStatus,
  OrchestratorMessage,
  OrchestratorDelegateRequest,
  OrchestratorSchedulerSnapshot,
  OrchestratorSession,
  OrchestratorTask,
  PersonaProfile,
} from "./lib/api";
import {
  activateOrchestratorSession,
  approveOrchestratorPlan,
  cancelOrchestratorSession,
  chat,
  completeOrchestratorDelegate,
  createOrchestratorSession,
  deleteOrchestratorSession,
  fetchOrchestratorMessages,
  fetchOrchestratorScheduler,
  fetchOrchestratorSessions,
  fetchGoals,
  fetchMessages,
  fetchState,
  fetchWorld,
  generateOrchestratorPlan,
  rejectOrchestratorPlan,
  removeChatFolderPermission,
  runOrchestratorConsoleCommand,
  resumeOrchestratorSession,
  resumeChat,
  sleep,
  stopOrchestratorDelegate,
  tickOrchestratorScheduler,
  upsertChatFolderPermission,
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
import { CapabilitiesPage } from "./pages/CapabilitiesPage";
import { MemoryPage } from "./pages/MemoryPage";
import { OrchestratorPage, type StopDelegateTaskRequest } from "./pages/OrchestratorPage";
import {
  addImportedProject,
  buildFolderPermissionPlan,
  loadImportedProjectRegistry,
  normalizeProjectPath,
  removeImportedProject,
  saveImportedProjectRegistry,
  setActiveImportedProject,
  type ImportedProjectRegistry,
} from "./lib/projects";
import { buildDelegateDebugInfo } from "./lib/orchestratorDelegateDebug";
import { runCodexDelegate, stopCodexDelegate } from "./lib/tauri/codexDelegate";
import {
  fsClearAllowedDirectory,
  fsSetAllowedDirectory,
  isTauriRuntime,
  pickDirectory,
  pickFiles,
} from "./lib/tauri";
import {
  appendOrchestratorDelta,
  finalizeOrchestratorMessage,
  markOrchestratorMessageFailed,
  mergeOrchestratorMessages,
  upsertOrchestratorStreamingMessage,
} from "./lib/orchestratorMessages";
import {
  createOrchestratorSendGuardState,
  getOrchestratorSendBlockReason,
  markOrchestratorSendFinish,
  markOrchestratorSendStart,
} from "./lib/orchestratorSendGuard";
import {
  createInitialOrchestratorConsoleState,
  orchestratorConsoleReducer,
  resolveActiveSessionId,
  resolveActiveTabDraft,
  resolveActiveWorkbenchTab,
} from "./lib/orchestratorConsoleState";
import {
  createEmptySessionHistoryFilter,
  type SessionHistoryFilter,
} from "./lib/orchestratorWorkbench";
import { loadChatToolboxSelectedSkills } from "./lib/chatToolboxPreferences";

type AppRoute =
  | "overview"
  | "chat"
  | "persona"
  | "memory"
  | "tools"
  | "capabilities"
  | "orchestrator";

const initialState: BeingState = {
  mode: "sleeping",
  focus_mode: "sleeping",
  current_thought: null,
  active_goal_ids: [],
  today_plan: null,
  last_action: null,
  self_programming_job: null,
  orchestrator_session: null,
};

const defaultOrchestratorScheduler: OrchestratorSchedulerSnapshot = {
  max_parallel_sessions: 2,
  running_sessions: 0,
  available_slots: 0,
  queued_sessions: 0,
  active_session_id: null,
  running_session_ids: [],
  queued_session_ids: [],
  verification_rollup: {
    total_sessions: 0,
    passed_sessions: 0,
    failed_sessions: 0,
    pending_sessions: 0,
  },
  policy_note: null,
};

const DELEGATE_TIMEOUT_SECONDS_BY_KIND: Record<OrchestratorTask["kind"], number> = {
  analyze: 20 * 60,
  implement: 45 * 60,
  test: 35 * 60,
  verify: 25 * 60,
  summarize: 15 * 60,
};

const DELEGATE_TIMEOUT_SECONDS_MIN = 30;
const DELEGATE_TIMEOUT_SECONDS_MAX = 60 * 60;
const DELEGATE_TIMEOUT_SECONDS_FALLBACK = 20 * 60;

type OrchestratorUIAction =
  | {
      type: "send_message";
      message: string;
      clearDraft: boolean;
    }
  | {
      type: "stop_task";
      payload: StopDelegateTaskRequest;
    };

export default function App() {
  const [route, setRoute] = useState<AppRoute>(() => resolveRoute(window.location.hash));
  const [state, setState] = useState<BeingState>(initialState);
  const [world, setWorld] = useState<InnerWorldState | null>(null);
  const [macConsoleStatus, setMacConsoleStatus] = useState<MacConsoleBootstrapStatus | null>(null);
  const [messages, setMessages] = useState<ChatEntry[]>([]);
  const [goals, setGoals] = useState<Goal[]>([]);
  const [orchestratorSessions, setOrchestratorSessions] = useState<OrchestratorSession[]>([]);
  const [orchestratorHistoryFilter, setOrchestratorHistoryFilter] = useState<SessionHistoryFilter>(() =>
    createEmptySessionHistoryFilter(),
  );
  const [orchestratorHistorySessions, setOrchestratorHistorySessions] = useState<OrchestratorSession[]>([]);
  const [orchestratorScheduler, setOrchestratorScheduler] = useState<OrchestratorSchedulerSnapshot>(
    defaultOrchestratorScheduler,
  );
  const [orchestratorMessagesBySession, setOrchestratorMessagesBySession] = useState<Record<string, OrchestratorMessage[]>>({});
  const [importedProjectRegistry, setImportedProjectRegistry] = useState<ImportedProjectRegistry>(() =>
    loadImportedProjectRegistry(),
  );
  const [isUpdatingProjects, setIsUpdatingProjects] = useState(false);
  const [projectControlError, setProjectControlError] = useState("");
  const [persona, setPersona] = useState<PersonaProfile | null>(null);
  const [draft, setDraft] = useState("");
  const [attachedFolders, setAttachedFolders] = useState<string[]>([]);
  const [attachedFiles, setAttachedFiles] = useState<string[]>([]);
  const [attachedImages, setAttachedImages] = useState<string[]>([]);
  const [orchestratorConsoleState, dispatchOrchestratorConsole] = useReducer(
    orchestratorConsoleReducer,
    undefined,
    createInitialOrchestratorConsoleState,
  );
  const [isSending, setIsSending] = useState(false);
  const [isOrchestratorSending, setIsOrchestratorSending] = useState(false);
  const [orchestratorSendNotice, setOrchestratorSendNotice] = useState("");
  const [error, setError] = useState("");
  const [theme, setTheme] = useState<"dark" | "light">(() => loadThemePreference());
  const [showBrandMenu, setShowBrandMenu] = useState(false);
  const [showAbout, setShowAbout] = useState(false);
  const [petVisible, setPetVisible] = useState(false);
  const pendingRequestMessageRef = useRef<string | null>(null);
  const schedulerTickInFlightRef = useRef(false);
  const delegateRunIdsRef = useRef(new Set<string>());
  const orchestratorFeedbackPollInFlightRef = useRef(false);
  const orchestratorSendGuardRef = useRef(createOrchestratorSendGuardState());
  const orchestratorSendNoticeTimerRef = useRef<number | null>(null);
  const hasAttemptedImportedProjectRestoreRef = useRef(false);
  const focusGoalTitle = resolveFocusGoalTitle(state, goals);
  const assistantName = persona?.name?.trim() || "小晏";
  const assistantIdentity = persona?.identity?.trim() || "AI Agent Desktop";
  const sessionList = normalizeOrchestratorSessions(orchestratorSessions);
  const activeOrchestratorTab = resolveActiveWorkbenchTab(orchestratorConsoleState);
  const activeOrchestratorSessionId = resolveActiveSessionId(orchestratorConsoleState);
  const orchestratorDraft = resolveActiveTabDraft(orchestratorConsoleState);
  const activeOrchestratorMessages =
    activeOrchestratorSessionId == null ? [] : orchestratorMessagesBySession[activeOrchestratorSessionId] ?? [];
  const activeImportedProjectPath = importedProjectRegistry.active_project_path;
  const shouldShowOrchestratorEntry =
    route === "orchestrator" ||
    state.focus_mode === "orchestrator" ||
    sessionList.length > 0 ||
    orchestratorConsoleState.tabs.length > 0;

  useEffect(() => {
    dispatchOrchestratorConsole({
      type: "sync_sessions",
      sessionIds: sessionList.map((session) => session.session_id),
      preferredSessionId: state.orchestrator_session?.session_id ?? null,
    });
  }, [sessionList, state.orchestrator_session?.session_id]);

  useEffect(() => {
    if (hasAttemptedImportedProjectRestoreRef.current) {
      return;
    }
    hasAttemptedImportedProjectRestoreRef.current = true;

    if (importedProjectRegistry.projects.length === 0) {
      return;
    }

    let cancelled = false;
    void restoreImportedProjectsToCore(importedProjectRegistry).catch((err) => {
      if (cancelled) {
        return;
      }
      const detail = err instanceof Error ? err.message : "unknown error";
      setError(`恢复已导入项目权限失败: ${detail}`);
    });

    return () => {
      cancelled = true;
    };
  }, [importedProjectRegistry]);

  useEffect(() => {
    let cancelled = false;

    async function syncRuntime() {
      try {
        const initialRoute = resolveRoute(window.location.hash);
        const [nextState, nextGoals, nextWorld] = await Promise.all([
          fetchState(),
          fetchGoals(),
          fetchWorld(),
        ]);

        if (cancelled) {
          return;
        }

        setState(nextState);
        setGoals(nextGoals.goals);
        setWorld(nextWorld);
        if (initialRoute === "chat") {
          void fetchMessages()
            .then((nextMessages) => {
              if (!cancelled) {
                setMessages((current) => syncMessagesFromRuntime(current, nextMessages.messages));
              }
            })
            .catch(() => {
              // Messages remain lazy-loaded when chat opens.
            });
        }
        if (initialRoute === "orchestrator") {
          void Promise.all([
            fetchOrchestratorSessions().catch(() => []),
            fetchOrchestratorScheduler().catch(() => defaultOrchestratorScheduler),
          ]).then(([nextOrchestratorSessions, nextOrchestratorScheduler]) => {
            if (cancelled) {
              return;
            }
            const normalizedSessions = normalizeOrchestratorSessions(nextOrchestratorSessions);
            setOrchestratorSessions(normalizedSessions);
            setOrchestratorHistorySessions(normalizedSessions);
            setOrchestratorScheduler(normalizeOrchestratorScheduler(nextOrchestratorScheduler));
          });
        }
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
            undefined,
            event.payload.reasoning_session_id,
            event.payload.reasoning_state,
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
            event.payload.reasoning_session_id,
            event.payload.reasoning_state,
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
            event.payload.knowledge_references,
            event.payload.reasoning_session_id,
            event.payload.reasoning_state,
          );
          return updated;
        });
        setError("");
        return;
      }

      if (event.type === "chat_failed") {
        setMessages((current) =>
          markAssistantMessageFailed(
            current,
            event.payload.assistant_message_id,
            event.payload.sequence,
            event.payload.reasoning_session_id,
            event.payload.reasoning_state,
          )
        );
        setError(event.payload.error);
        return;
      }

      if (event.type === "orchestrator_message_appended") {
        setOrchestratorMessagesBySession((current) => ({
          ...current,
          [event.payload.session_id]: mergeOrchestratorMessages(current[event.payload.session_id] ?? [], [event.payload]),
        }));
        setError("");
        return;
      }

      if (event.type === "orchestrator_message_started") {
        setOrchestratorMessagesBySession((current) => ({
          ...current,
          [event.payload.session_id]: upsertOrchestratorStreamingMessage(
            current[event.payload.session_id] ?? [],
            event.payload.session_id,
            event.payload.assistant_message_id,
            event.payload.sequence,
          ),
        }));
        setError("");
        return;
      }

      if (event.type === "orchestrator_message_delta") {
        setOrchestratorMessagesBySession((current) => ({
          ...current,
          [event.payload.session_id]: appendOrchestratorDelta(
            current[event.payload.session_id] ?? [],
            event.payload.assistant_message_id,
            event.payload.delta,
          ),
        }));
        setError("");
        return;
      }

      if (event.type === "orchestrator_message_completed") {
        setOrchestratorMessagesBySession((current) => ({
          ...current,
          [event.payload.session_id]: finalizeOrchestratorMessage(
            current[event.payload.session_id] ?? [],
            event.payload.assistant_message_id,
            event.payload.content,
            event.payload.blocks,
          ),
        }));
        setError("");
        return;
      }

      if (event.type === "orchestrator_message_failed") {
        setOrchestratorMessagesBySession((current) => ({
          ...current,
          [event.payload.session_id]: markOrchestratorMessageFailed(
            current[event.payload.session_id] ?? [],
            event.payload.assistant_message_id,
          ),
        }));
        setError(event.payload.error);
        return;
      }

      if (event.type === "orchestrator_session_updated") {
        setOrchestratorSessions((current) =>
          upsertOrchestratorSession(normalizeOrchestratorSessions(current), event.payload),
        );
        void refreshOrchestratorSessionHistory().catch(() => {
          // Ignore history refresh errors in realtime path.
        });
        void refreshOrchestratorScheduler();
        return;
      }

      const runtimePayload =
        event.type === "snapshot" ? event.payload.runtime : event.type === "runtime_updated" ? event.payload : null;
      if (!runtimePayload) {
        return;
      }

      setState(runtimePayload.state);
      setMessages((current) => syncMessagesFromRuntime(current, runtimePayload.messages));
      setGoals(runtimePayload.goals);
      setWorld(runtimePayload.world);
      if (runtimePayload.mac_console_status !== undefined) {
        setMacConsoleStatus(runtimePayload.mac_console_status ?? null);
      }
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

  useEffect(() => {
    if (route !== "chat") {
      return;
    }

    let cancelled = false;
    void fetchMessages()
      .then((nextMessages) => {
        if (!cancelled) {
          setMessages((current) => syncMessagesFromRuntime(current, nextMessages.messages));
        }
      })
      .catch((err) => {
        if (!cancelled) {
          console.error("加载聊天消息失败:", err);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [route]);

  useEffect(() => {
    if (route !== "orchestrator") {
      return;
    }

    let cancelled = false;
    void Promise.all([
      fetchOrchestratorSessions().catch(() => []),
      fetchOrchestratorScheduler().catch(() => defaultOrchestratorScheduler),
    ])
      .then(([nextOrchestratorSessions, nextOrchestratorScheduler]) => {
        if (cancelled) {
          return;
        }
        const normalizedSessions = normalizeOrchestratorSessions(nextOrchestratorSessions);
        setOrchestratorSessions(normalizedSessions);
        setOrchestratorHistorySessions(normalizedSessions);
        setOrchestratorScheduler(normalizeOrchestratorScheduler(nextOrchestratorScheduler));
      })
      .catch((err) => {
        if (!cancelled) {
          console.error("加载主控数据失败:", err);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [route]);

  useEffect(() => {
    if (!activeOrchestratorSessionId) {
      return;
    }

    let cancelled = false;
    void fetchOrchestratorMessages(activeOrchestratorSessionId)
      .then((nextMessages) => {
        if (cancelled) {
          return;
        }
        setOrchestratorMessagesBySession((current) => ({
          ...current,
          [activeOrchestratorSessionId]: mergeOrchestratorMessages(current[activeOrchestratorSessionId] ?? [], nextMessages),
        }));
      })
      .catch((err) => {
        if (!cancelled) {
          console.error("加载主控消息失败:", err);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [activeOrchestratorSessionId]);

  // 主题切换：更新 DOM 和 localStorage
  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("theme", theme);
  }, [theme]);

  useEffect(() => {
    const syncRoute = () => {
      const nextRoute = resolveRoute(window.location.hash);
      setRoute(nextRoute);

      if (window.location.hash === "#/history") {
        window.location.hash = routeToHash("overview");
      }
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

  useEffect(() => {
    const hasDispatchingSession = sessionList.some((session) => session.status === "dispatching");
    const hasQueuedSession = sessionList.some(
      (session) => session.coordination?.mode === "queued" || session.coordination?.mode === "preempted",
    );
    const hasSchedulerDemand =
      hasDispatchingSession || (hasQueuedSession && orchestratorScheduler.available_slots > 0);
    if (!hasSchedulerDemand || schedulerTickInFlightRef.current) {
      return;
    }

    schedulerTickInFlightRef.current = true;
    void (async () => {
      try {
        const snapshot = await tickOrchestratorScheduler();
        setOrchestratorScheduler(normalizeOrchestratorScheduler(snapshot));
        await Promise.all([
          refreshRuntimeState(),
          refreshOrchestratorSessions(),
          refreshOrchestratorScheduler(),
          activeOrchestratorSessionId ? refreshOrchestratorMessages(activeOrchestratorSessionId) : Promise.resolve(),
        ]);
      } catch (err) {
        setError(err instanceof Error ? err.message : "主控调度失败");
      } finally {
        schedulerTickInFlightRef.current = false;
      }
    })();
  }, [orchestratorScheduler.available_slots, sessionList]);

  useEffect(() => {
    if (route !== "orchestrator" || !activeOrchestratorSessionId) {
      return;
    }

    const activeSession = sessionList.find((session) => session.session_id === activeOrchestratorSessionId);
    const isTerminal = activeSession != null && ["completed", "failed", "cancelled"].includes(activeSession.status);
    if (isTerminal && !isOrchestratorSending) {
      return;
    }

    let cancelled = false;
    const sessionId = activeOrchestratorSessionId;
    const timer = window.setInterval(() => {
      if (cancelled || orchestratorFeedbackPollInFlightRef.current) {
        return;
      }
      orchestratorFeedbackPollInFlightRef.current = true;
      void Promise.all([
        refreshOrchestratorSessions(),
        refreshOrchestratorScheduler(),
        refreshOrchestratorMessages(sessionId),
      ])
        .catch((err) => {
          if (!cancelled) {
            console.warn("主控回执轮询失败:", err);
          }
        })
        .finally(() => {
          orchestratorFeedbackPollInFlightRef.current = false;
        });
    }, 2500);

    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [route, activeOrchestratorSessionId, sessionList, isOrchestratorSending]);

  useEffect(() => {
    for (const session of sessionList) {
      if (!session.plan) {
        continue;
      }
      const runningTasks = session.plan.tasks.filter(
        (task) => task.status === "running" && typeof task.delegate_run_id === "string" && task.delegate_run_id.length > 0,
      );
      for (const runningTask of runningTasks) {
        if (!runningTask.delegate_run_id) {
          continue;
        }
        if (delegateRunIdsRef.current.has(runningTask.delegate_run_id)) {
          continue;
        }

        const delegateRunId = runningTask.delegate_run_id;
        delegateRunIdsRef.current.add(delegateRunId);

        void (async () => {
          try {
            const delegateRequest = extractDelegateRequest(runningTask);
            const delegatePrompt = extractDelegatePrompt(runningTask, delegateRequest, session);
            const delegateTimeoutSeconds = resolveDelegateTimeoutSeconds(runningTask);
            const delegateResult = await runCodexDelegate({
              prompt: delegatePrompt,
              projectPath: session.project_path,
              runId: delegateRunId,
              outputSchema: delegateRequest.output_schema,
              timeoutSeconds: delegateTimeoutSeconds,
            });

            try {
              await completeOrchestratorDelegate({
                session_id: session.session_id,
                task_id: runningTask.task_id,
                delegate_run_id: delegateRunId,
                result: {
                  status: delegateResult.status,
                  summary: delegateResult.summary,
                  changed_files: delegateResult.changed_files,
                  command_results: delegateResult.command_results.map((item) => ({
                    command: item.command,
                    success: item.success,
                    exit_code: item.exit_code,
                    stdout: item.stdout,
                    stderr: item.stderr,
                    duration_ms: item.duration_ms,
                  })),
                  followup_needed: delegateResult.followup_needed,
                  error: delegateResult.error ?? null,
                  debug: buildDelegateDebugInfo(delegateResult.stdout, delegateResult.stderr) ?? null,
                },
              });
            } catch (completeError) {
              if (isRecoverableDelegateCompletionConflict(completeError)) {
                await Promise.all([
                  refreshRuntimeState(),
                  refreshOrchestratorSessions(),
                  refreshOrchestratorScheduler(),
                  refreshOrchestratorMessages(session.session_id),
                ]);
                return;
              }
              throw completeError;
            }
            await Promise.all([
              refreshRuntimeState(),
              refreshOrchestratorSessions(),
              refreshOrchestratorScheduler(),
              refreshOrchestratorMessages(session.session_id),
            ]);
          } catch (err) {
            if (isRecoverableDelegateCompletionConflict(err)) {
              await Promise.all([
                refreshRuntimeState(),
                refreshOrchestratorSessions(),
                refreshOrchestratorScheduler(),
                refreshOrchestratorMessages(session.session_id),
              ]);
              return;
            }
            const message = err instanceof Error ? err.message : "Codex delegate 执行失败";
            try {
              await completeOrchestratorDelegate({
                session_id: session.session_id,
                task_id: runningTask.task_id,
                delegate_run_id: delegateRunId,
                result: {
                  status: "failed",
                  summary: "Codex delegate 执行失败",
                  changed_files: [],
                  command_results: [],
                  followup_needed: [],
                  error: message,
                },
              });
              await Promise.all([
                refreshRuntimeState(),
                refreshOrchestratorSessions(),
                refreshOrchestratorScheduler(),
                refreshOrchestratorMessages(session.session_id),
              ]);
            } catch (completeError) {
              if (isRecoverableDelegateCompletionConflict(completeError)) {
                await Promise.all([
                  refreshRuntimeState(),
                  refreshOrchestratorSessions(),
                  refreshOrchestratorScheduler(),
                  refreshOrchestratorMessages(session.session_id),
                ]);
                return;
              }
              const merged =
                completeError instanceof Error
                  ? `${message}; ${completeError.message}`
                  : message;
              setError(merged);
              return;
            }
            setError(message);
          } finally {
            delegateRunIdsRef.current.delete(delegateRunId);
          }
        })();
      }
    }
  }, [sessionList]);

  useEffect(() => {
    return () => {
      if (orchestratorSendNoticeTimerRef.current != null) {
        window.clearTimeout(orchestratorSendNoticeTimerRef.current);
      }
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

  async function handleSend(options?: ChatSendOptions) {
    const content = draft.trim();
    if (!content) {
      return;
    }

    setError("");
    setDraft("");
    setIsSending(true);
    let pendingUserMessageId: string | null = null;

    try {
      if (isExplicitOrchestratorEntry(content)) {
        await createAndOpenOrchestratorSession(content);
        handleNavigate("orchestrator");
        return;
      }

      const userMessage: ChatEntry = {
        id: `user-${Date.now()}`,
        role: "user",
        content,
      };
      pendingUserMessageId = userMessage.id;

      const normalizedAttachedFolders = normalizeAttachedPaths(attachedFolders);
      const normalizedAttachedFiles = normalizeAttachedPaths(attachedFiles);
      const normalizedAttachedImages = normalizeAttachedPaths(attachedImages);
      const attachments = buildChatAttachments(
        normalizedAttachedFolders,
        normalizedAttachedFiles,
        normalizedAttachedImages,
      );
      const requestBody: ChatRequestBody =
        attachments.length > 0 ? { message: content, attachments } : { message: content };
      if (options?.continuousReasoningEnabled) {
        requestBody.reasoning = { enabled: true };
      }
      if (Array.isArray(options?.mcpServerIds)) {
        const normalizedMcpServerIds = Array.from(
          new Set(
            options.mcpServerIds
              .filter((serverId): serverId is string => typeof serverId === "string")
              .map((serverId) => serverId.trim())
              .filter((serverId) => serverId.length > 0),
          ),
        );
        requestBody.mcp_servers = normalizedMcpServerIds;
      }
      const selectedSkills = Array.from(
        new Set(
          loadChatToolboxSelectedSkills()
            .filter((name): name is string => typeof name === "string")
            .map((name) => name.trim())
            .filter((name) => name.length > 0),
        ),
      );
      if (selectedSkills.length > 0) {
        requestBody.skills = selectedSkills;
      }
      setMessages((current) => [...current, { ...userMessage, retryRequestBody: requestBody }]);
      pendingRequestMessageRef.current = content;
      await chat(requestBody);
      setAttachedFiles([]);
      setAttachedImages([]);
      setAttachedFolders([]);
    } catch (err) {
      if (pendingUserMessageId) {
        setMessages((current) =>
          current.map((message) =>
            message.id === pendingUserMessageId ? { ...message, state: "failed" } : message,
          ),
        );
      }
      setError(err instanceof Error ? err.message : "发送失败");
    } finally {
      setIsSending(false);
    }
  }

  async function createAndOpenOrchestratorSession(goal: string) {
    const normalizedGoal = goal.trim();
    if (!normalizedGoal) {
      throw new Error("会话目标不能为空");
    }
    if (!activeImportedProjectPath) {
      throw new Error("进入主控前需要先在主控工作台导入并激活一个项目");
    }

    await ensureOrchestratorProjectPermission(activeImportedProjectPath);
    const session = await createOrchestratorSession({
      goal: normalizedGoal,
      project_path: activeImportedProjectPath,
    });
    dispatchOrchestratorConsole({
      type: "ensure_session_tab",
      sessionId: session.session_id,
      activate: true,
    });
    await generateOrchestratorPlan(session.session_id);
    await Promise.all([
      refreshRuntimeState(),
      refreshOrchestratorSessions(),
      refreshOrchestratorScheduler(),
      refreshOrchestratorMessages(session.session_id),
    ]);
  }

  const handleRetry = useCallback(async (message: ChatEntry) => {
    if (message.role !== "user") {
      return;
    }

    const requestBody: ChatRequestBody = message.retryRequestBody ?? { message: message.content };
    setError("");
    setIsSending(true);
    setMessages((current) =>
      current.map((entry) => (entry.id === message.id ? { ...entry, state: undefined } : entry)),
    );

    try {
      pendingRequestMessageRef.current = requestBody.message;
      await chat(requestBody);
      setAttachedFiles([]);
      setAttachedImages([]);
      setAttachedFolders([]);
    } catch (err) {
      setMessages((current) =>
        current.map((entry) => (entry.id === message.id ? { ...entry, state: "failed" } : entry)),
      );
      setError(err instanceof Error ? err.message : "发送失败");
    } finally {
      setIsSending(false);
    }
  }, []);

  const handleResume = useCallback(async (message: ChatEntry) => {
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
        reasoning_session_id: message.reasoningSessionId,
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "继续生成失败");
    } finally {
      setIsSending(false);
    }
  }, []);

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

  async function refreshRuntimeState() {
    const refreshedState = await fetchState();
    setState(refreshedState);
  }

  async function handlePersonaUpdated() {
    try {
      const [nextState, nextMessages, nextGoals, nextWorld] = await Promise.all([
        fetchState(),
        fetchMessages(),
        fetchGoals(),
        fetchWorld(),
      ]);

      setState(nextState);
      setMessages(syncMessagesFromRuntime([], nextMessages.messages));
      setGoals(nextGoals.goals);
      setWorld(nextWorld);
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "同步失败");
    }
  }

  async function refreshOrchestratorSessionHistory(filter: SessionHistoryFilter = orchestratorHistoryFilter) {
    const historySessions = await fetchOrchestratorSessions(toOrchestratorSessionListFilters(filter));
    setOrchestratorHistorySessions(normalizeOrchestratorSessions(historySessions));
  }

  async function refreshOrchestratorSessions() {
    const allSessions = normalizeOrchestratorSessions(await fetchOrchestratorSessions());
    setOrchestratorSessions(allSessions);
    await refreshOrchestratorSessionHistory();
  }

  async function refreshOrchestratorScheduler() {
    const refreshedScheduler = await fetchOrchestratorScheduler().catch(() => defaultOrchestratorScheduler);
    setOrchestratorScheduler(normalizeOrchestratorScheduler(refreshedScheduler));
  }

  async function refreshOrchestratorMessages(sessionId: string) {
    const refreshedMessages = await fetchOrchestratorMessages(sessionId);
    setOrchestratorMessagesBySession((current) => ({
      ...current,
      [sessionId]: mergeOrchestratorMessages(current[sessionId] ?? [], refreshedMessages),
    }));
  }

  function handleOrchestratorHistoryFilterChange(next: SessionHistoryFilter) {
    setOrchestratorHistoryFilter(next);
  }

  async function handleApplyOrchestratorHistoryFilter(next: SessionHistoryFilter) {
    try {
      setError("");
      setOrchestratorHistoryFilter(next);
      await refreshOrchestratorSessionHistory(next);
    } catch (err) {
      setError(err instanceof Error ? err.message : "会话历史筛选失败");
    }
  }

  function handleOrchestratorDraftChange(value: string) {
    if (!activeOrchestratorTab) {
      return;
    }
    dispatchOrchestratorConsole({
      type: "set_draft",
      tabId: activeOrchestratorTab.tab_id,
      draft: value,
    });
  }

  function handleActivateOrchestratorTab(tabId: string) {
    dispatchOrchestratorConsole({
      type: "activate_tab",
      tabId,
    });
  }

  function handleCloseOrchestratorTab(tabId: string) {
    dispatchOrchestratorConsole({
      type: "close_tab",
      tabId,
    });
  }

  function handleCreateBlankOrchestratorTab() {
    dispatchOrchestratorConsole({
      type: "add_blank_tab",
    });
  }

  async function handleApproveOrchestratorPlan(sessionId: string) {
    try {
      setError("");
      await approveOrchestratorPlan(sessionId);
      await Promise.all([
        refreshRuntimeState(),
        refreshOrchestratorSessions(),
        refreshOrchestratorScheduler(),
        refreshOrchestratorMessages(sessionId),
      ]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "主控计划审批失败");
    }
  }

  async function handleRejectOrchestratorPlan(sessionId: string) {
    try {
      setError("");
      await rejectOrchestratorPlan(sessionId);
      await Promise.all([
        refreshRuntimeState(),
        refreshOrchestratorSessions(),
        refreshOrchestratorScheduler(),
        refreshOrchestratorMessages(sessionId),
      ]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "主控计划拒绝失败");
    }
  }

  async function handleCancelOrchestrator(sessionId: string) {
    try {
      setError("");
      await cancelOrchestratorSession(sessionId);
      await Promise.all([refreshRuntimeState(), refreshOrchestratorSessions(), refreshOrchestratorScheduler()]);
      handleNavigate("chat");
    } catch (err) {
      setError(err instanceof Error ? err.message : "退出主控失败");
    }
  }

  async function handleActivateOrchestratorSession(sessionId: string) {
    try {
      setError("");
      await activateOrchestratorSession(sessionId);
      dispatchOrchestratorConsole({
        type: "ensure_session_tab",
        sessionId,
        activate: true,
      });
      await Promise.all([
        refreshRuntimeState(),
        refreshOrchestratorSessions(),
        refreshOrchestratorScheduler(),
        refreshOrchestratorMessages(sessionId),
      ]);
      handleNavigate("orchestrator");
    } catch (err) {
      setError(err instanceof Error ? err.message : "切换主控会话失败");
    }
  }

  async function handleResumeOrchestratorSession(sessionId: string) {
    try {
      setError("");
      await resumeOrchestratorSession(sessionId);
      dispatchOrchestratorConsole({
        type: "ensure_session_tab",
        sessionId,
        activate: true,
      });
      await Promise.all([
        refreshRuntimeState(),
        refreshOrchestratorSessions(),
        refreshOrchestratorScheduler(),
        refreshOrchestratorMessages(sessionId),
      ]);
      handleNavigate("orchestrator");
    } catch (err) {
      setError(err instanceof Error ? err.message : "恢复主控会话失败");
    }
  }

  async function handleCreateOrchestratorSession(goal: string) {
    try {
      setError("");
      dispatchOrchestratorConsole({
        type: "add_blank_tab",
        draft: goal || "进入主控，处理当前项目",
      });
      handleNavigate("orchestrator");
    } catch (err) {
      setError(err instanceof Error ? err.message : "创建主控会话失败");
    }
  }

  async function handleDeleteOrchestratorSession(sessionId: string) {
    const confirmed = window.confirm("确认删除该历史会话吗？会同时清空该会话的消息记录。");
    if (!confirmed) {
      return;
    }

    try {
      setError("");
      await deleteOrchestratorSession(sessionId);
      dispatchOrchestratorConsole({
        type: "remove_session_tabs",
        sessionId,
      });
      setOrchestratorMessagesBySession((current) => {
        const next = { ...current };
        delete next[sessionId];
        return next;
      });
      await Promise.all([
        refreshRuntimeState(),
        refreshOrchestratorSessions(),
        refreshOrchestratorScheduler(),
      ]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "删除主控会话失败");
    }
  }

  function applyImportedProjectRegistry(nextRegistry: ImportedProjectRegistry) {
    setImportedProjectRegistry(nextRegistry);
    saveImportedProjectRegistry(nextRegistry);
  }

  async function syncImportedProjectPermissions(
    previousRegistry: ImportedProjectRegistry,
    nextRegistry: ImportedProjectRegistry,
  ) {
    const nextPlan = buildFolderPermissionPlan(nextRegistry);
    for (const permission of nextPlan) {
      await upsertChatFolderPermission(permission.path, permission.access_level);
    }

    const previousPaths = new Set(previousRegistry.projects.map((project) => normalizeProjectPath(project.path)));
    const nextPaths = new Set(nextRegistry.projects.map((project) => normalizeProjectPath(project.path)));
    for (const path of previousPaths) {
      if (!path || nextPaths.has(path)) {
        continue;
      }
      await removeChatFolderPermission(path);
    }
  }

  async function handleImportProjectToOrchestrator() {
    if (!isTauriRuntime()) {
      setProjectControlError("当前环境不是 Tauri 宿主，无法导入本地项目。");
      return;
    }
    setProjectControlError("");
    setIsUpdatingProjects(true);
    try {
      const selected = await pickDirectory();
      if (!selected) {
        return;
      }

      const previousRegistry = importedProjectRegistry;
      const nextRegistry = addImportedProject(previousRegistry, selected);
      const normalized = await fsSetAllowedDirectory(selected);
      const appliedRegistry = setActiveImportedProject(nextRegistry, normalized);
      await syncImportedProjectPermissions(previousRegistry, appliedRegistry);
      applyImportedProjectRegistry(appliedRegistry);
    } catch (err) {
      const detail = err instanceof Error ? err.message : "导入项目失败";
      setProjectControlError(detail);
      setError(detail);
    } finally {
      setIsUpdatingProjects(false);
    }
  }

  async function handleActivateOrchestratorProject(path: string) {
    if (!isTauriRuntime()) {
      setProjectControlError("当前环境不是 Tauri 宿主，无法切换主控项目。");
      return;
    }
    setProjectControlError("");
    setIsUpdatingProjects(true);
    try {
      const normalizedPath = normalizeProjectPath(path);
      const previousRegistry = importedProjectRegistry;
      const nextRegistry = setActiveImportedProject(previousRegistry, normalizedPath);
      if (nextRegistry.active_project_path === previousRegistry.active_project_path) {
        return;
      }

      await fsSetAllowedDirectory(normalizedPath);
      await syncImportedProjectPermissions(previousRegistry, nextRegistry);
      applyImportedProjectRegistry(nextRegistry);
    } catch (err) {
      const detail = err instanceof Error ? err.message : "切换主控项目失败";
      setProjectControlError(detail);
      setError(detail);
    } finally {
      setIsUpdatingProjects(false);
    }
  }

  async function handleRemoveOrchestratorProject(path: string) {
    if (!isTauriRuntime()) {
      setProjectControlError("当前环境不是 Tauri 宿主，无法移除项目。");
      return;
    }
    setProjectControlError("");
    setIsUpdatingProjects(true);
    try {
      const normalizedPath = normalizeProjectPath(path);
      const previousRegistry = importedProjectRegistry;
      const previousActivePath = normalizeProjectPath(previousRegistry.active_project_path ?? "");
      const nextRegistry = removeImportedProject(previousRegistry, normalizedPath);
      if (nextRegistry.projects.length === previousRegistry.projects.length) {
        return;
      }

      if (previousActivePath === normalizedPath) {
        if (nextRegistry.active_project_path) {
          await fsSetAllowedDirectory(nextRegistry.active_project_path);
        } else {
          await fsClearAllowedDirectory();
        }
      }

      await syncImportedProjectPermissions(previousRegistry, nextRegistry);
      applyImportedProjectRegistry(nextRegistry);
    } catch (err) {
      const detail = err instanceof Error ? err.message : "移除项目失败";
      setProjectControlError(detail);
      setError(detail);
    } finally {
      setIsUpdatingProjects(false);
    }
  }

  async function handlePickChatFolder() {
    if (!isTauriRuntime()) {
      setError("当前环境不是 Tauri 宿主，无法选择文件夹。");
      return;
    }

    setError("");
    try {
      const selected = await pickDirectory();
      if (!selected) {
        return;
      }

      const normalizedPath = normalizeProjectPath(selected);
      await upsertChatFolderPermission(normalizedPath, "read_only");
      setAttachedFolders((current) => (current.includes(normalizedPath) ? current : [...current, normalizedPath]));
    } catch (err) {
      setError(err instanceof Error ? err.message : "添加文件夹失败");
    }
  }

  async function handlePickChatFiles() {
    if (!isTauriRuntime()) {
      setError("当前环境不是 Tauri 宿主，无法选择文件。");
      return;
    }

    setError("");
    try {
      const selected = await pickFiles({
        title: "选择附件文件",
        filters: [
          {
            name: "文档与代码",
            extensions: ["txt", "md", "markdown", "json", "yaml", "yml", "toml", "csv", "log", "pdf", "py", "ts", "tsx", "js", "jsx"],
          },
        ],
        multiple: true,
      });
      if (selected.length === 0) {
        return;
      }

      const normalized = normalizeAttachedPaths(selected);
      const parentFolders = new Set(
        normalized
          .map((path) => resolveParentDirectory(path))
          .filter((path): path is string => Boolean(path)),
      );
      for (const folderPath of parentFolders) {
        await upsertChatFolderPermission(folderPath, "read_only");
      }
      setAttachedFiles((current) => mergeUniquePaths(current, normalized));
    } catch (err) {
      setError(err instanceof Error ? err.message : "添加文件失败");
    }
  }

  async function handlePickChatImages() {
    if (!isTauriRuntime()) {
      setError("当前环境不是 Tauri 宿主，无法选择图片。");
      return;
    }

    setError("");
    try {
      const selected = await pickFiles({
        title: "选择图片附件",
        filters: [
          {
            name: "图片",
            extensions: ["png", "jpg", "jpeg", "webp", "gif"],
          },
        ],
        multiple: true,
      });
      if (selected.length === 0) {
        return;
      }

      const normalized = normalizeAttachedPaths(selected);
      const parentFolders = new Set(
        normalized
          .map((path) => resolveParentDirectory(path))
          .filter((path): path is string => Boolean(path)),
      );
      for (const folderPath of parentFolders) {
        await upsertChatFolderPermission(folderPath, "read_only");
      }
      setAttachedImages((current) => mergeUniquePaths(current, normalized));
    } catch (err) {
      setError(err instanceof Error ? err.message : "添加图片失败");
    }
  }

  function handleRemoveAttachedFolder(path: string) {
    setAttachedFolders((current) => current.filter((item) => item !== path));
  }

  function handleRemoveAttachedFile(path: string) {
    setAttachedFiles((current) => current.filter((item) => item !== path));
  }

  function handleRemoveAttachedImage(path: string) {
    setAttachedImages((current) => current.filter((item) => item !== path));
  }

  function scheduleOrchestratorSendNotice(message: string) {
    setOrchestratorSendNotice(message);
    if (orchestratorSendNoticeTimerRef.current != null) {
      window.clearTimeout(orchestratorSendNoticeTimerRef.current);
    }
    orchestratorSendNoticeTimerRef.current = window.setTimeout(() => {
      setOrchestratorSendNotice("");
      orchestratorSendNoticeTimerRef.current = null;
    }, 1800);
  }

  async function sendOrchestratorMessage(
    content: string,
    options: { clearDraft: boolean },
  ): Promise<void> {
    const activeTab = activeOrchestratorTab;
    const normalizedContent = content.trim();
    if (!activeTab || !normalizedContent) {
      return;
    }
    const guardScopeId = activeTab.type === "session" ? activeTab.session_id : activeTab.tab_id;

    const nowMs = Date.now();
    const blockReason = getOrchestratorSendBlockReason(
      orchestratorSendGuardRef.current,
      guardScopeId,
      normalizedContent,
      nowMs,
    );
    if (blockReason === "duplicate_inflight") {
      scheduleOrchestratorSendNotice("同一条主控指令正在发送中，已为你拦截重复点击。");
      return;
    }
    if (blockReason === "duplicate_cooldown") {
      scheduleOrchestratorSendNotice("刚发送过同一条主控指令，已拦截重复提交。");
      return;
    }
    if (blockReason !== null) {
      return;
    }
    markOrchestratorSendStart(orchestratorSendGuardRef.current, guardScopeId, normalizedContent, nowMs);

    setError("");
    setOrchestratorSendNotice("");
    if (options.clearDraft) {
      dispatchOrchestratorConsole({
        type: "set_draft",
        tabId: activeTab.tab_id,
        draft: "",
      });
    }
    setIsOrchestratorSending(true);

    try {
      if (activeTab.type === "blank" && !activeImportedProjectPath) {
        throw new Error("主控项目未激活，请先在会话历史侧栏设置主控项目。");
      }
      const response = await runOrchestratorConsoleCommand({
        message: normalizedContent,
        session_id: activeTab.type === "session" ? activeTab.session_id : undefined,
        project_path: activeTab.type === "blank" ? activeImportedProjectPath : undefined,
      });
      const sessionId = response.session.session_id;
      if (activeTab.type === "blank") {
        dispatchOrchestratorConsole({
          type: "convert_blank_to_session",
          tabId: activeTab.tab_id,
          sessionId,
        });
      } else {
        dispatchOrchestratorConsole({
          type: "ensure_session_tab",
          sessionId,
          activate: false,
        });
      }
      await Promise.all([
        refreshOrchestratorSessions(),
        refreshOrchestratorScheduler(),
        refreshOrchestratorMessages(sessionId),
      ]);
    } catch (err) {
      if (options.clearDraft) {
        dispatchOrchestratorConsole({
          type: "set_draft",
          tabId: activeTab.tab_id,
          draft: normalizedContent,
        });
      }
      setError(err instanceof Error ? err.message : "主控消息发送失败");
    } finally {
      markOrchestratorSendFinish(orchestratorSendGuardRef.current, guardScopeId, normalizedContent);
      setIsOrchestratorSending(false);
    }
  }

  async function handleStopOrchestratorDelegateTask(payload: StopDelegateTaskRequest): Promise<void> {
    const stopReason = "主控手动停止运行任务";
    try {
      setError("");
      try {
        await stopCodexDelegate(payload.runId, stopReason);
      } catch (tauriStopError) {
        if (!isIgnorableLocalStopError(tauriStopError)) {
          throw tauriStopError;
        }
      }
      await stopOrchestratorDelegate({
        session_id: payload.sessionId,
        task_id: payload.taskId,
        delegate_run_id: payload.runId,
        reason: stopReason,
      });
      await Promise.all([
        refreshRuntimeState(),
        refreshOrchestratorSessions(),
        refreshOrchestratorScheduler(),
        refreshOrchestratorMessages(payload.sessionId),
      ]);
    } catch (err) {
      if (isRecoverableDelegateStopConflict(err)) {
        await Promise.all([
          refreshRuntimeState(),
          refreshOrchestratorSessions(),
          refreshOrchestratorScheduler(),
          refreshOrchestratorMessages(payload.sessionId),
        ]);
        return;
      }
      const message = err instanceof Error ? err.message : "停止 delegate 任务失败";
      setError(message);
      throw err;
    }
  }

  async function dispatchOrchestratorAction(action: OrchestratorUIAction): Promise<void> {
    if (action.type === "send_message") {
      await sendOrchestratorMessage(action.message.trim(), { clearDraft: action.clearDraft });
      return;
    }
    await handleStopOrchestratorDelegateTask(action.payload);
  }

  async function handleSendOrchestratorMessage() {
    await dispatchOrchestratorAction({
      type: "send_message",
      message: orchestratorDraft,
      clearDraft: true,
    });
  }

  async function handleSendOrchestratorQuickMessage(message: string) {
    await dispatchOrchestratorAction({
      type: "send_message",
      message,
      clearDraft: false,
    });
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
                    handleNavigate("persona");
                    setShowBrandMenu(false);
                  }}
                >
                  <span>🎭</span>
                  <span>人格设置</span>
                </button>
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
        </nav>

        {shouldShowOrchestratorEntry ? (
          <div className="app-sidebar__section">
            <div className="app-sidebar__section-title">可选入口</div>
            <div className="app-sidebar__actions">
              <button
                className={`app-sidebar__action-btn ${route === "memory" ? "app-sidebar__action-btn--primary" : ""}`}
                onClick={() => handleNavigate("memory")}
                type="button"
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M12 2a10 10 0 1 0 10 10H12V2z" />
                  <path d="M12 2a10 10 0 0 1 10 10" />
                  <path d="M12 12L2.5 12" />
                </svg>
                记忆库
              </button>
              <button
                className={`app-sidebar__action-btn ${route === "orchestrator" ? "app-sidebar__action-btn--primary" : ""}`}
                onClick={() => handleNavigate("orchestrator")}
                type="button"
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M4 6h16M4 12h10M4 18h7" />
                  <path d="M17 9l3 3-3 3" />
                </svg>
                主控工作台
              </button>
            </div>
            <p className="app-sidebar__section-hint">
              记忆、人格配置和高自治能力保留为次级入口，避免默认导航承载治理后台。
            </p>
          </div>
        ) : (
          <div className="app-sidebar__section">
            <div className="app-sidebar__section-title">可选入口</div>
            <div className="app-sidebar__actions">
              <button
                className={`app-sidebar__action-btn ${route === "memory" ? "app-sidebar__action-btn--primary" : ""}`}
                onClick={() => handleNavigate("memory")}
                type="button"
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M12 2a10 10 0 1 0 10 10H12V2z" />
                  <path d="M12 2a10 10 0 0 1 10 10" />
                  <path d="M12 12L2.5 12" />
                </svg>
                记忆库
              </button>
            </div>
            <p className="app-sidebar__section-hint">
              记忆、人格配置和高自治能力保留为次级入口，避免默认导航承载治理后台。
            </p>
          </div>
        )}

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
        {route === "orchestrator" && orchestratorSendNotice ? (
          <div className="notice-banner">{orchestratorSendNotice}</div>
        ) : null}

        {route === "chat" ? (
          <ChatPanel
            assistantName={assistantName}
            draft={draft}
            focusGoalTitle={focusGoalTitle}
            focusModeLabel={renderFocusModeLabel(state.focus_mode)}
            isSending={isSending}
            messages={messages}
            attachedFolders={attachedFolders}
            attachedFiles={attachedFiles}
            attachedImages={attachedImages}
            modeLabel={isAwake ? "运行中" : "休眠中"}
            todayPlan={state.today_plan}
            activeGoals={goals.filter(g => g.status === "active")}
            onDraftChange={setDraft}
            onSend={handleSend}
            onPickFolder={handlePickChatFolder}
            onPickFile={handlePickChatFiles}
            onPickImage={handlePickChatImages}
            onRemoveAttachedFolder={handleRemoveAttachedFolder}
            onRemoveAttachedFile={handleRemoveAttachedFile}
            onRemoveAttachedImage={handleRemoveAttachedImage}
            onResume={handleResume}
            onRetry={handleRetry}
            onCompleteGoal={(goalId) => handleUpdateGoalStatus(goalId, "completed")}
          />
        ) : route === "persona" ? (
          <PersonaPanel
            onPersonaUpdated={() => {
              void handlePersonaUpdated();
            }}
            assistantName={assistantName}
            petEnabled={persona?.features?.avatar_enabled ?? false}
            petVisible={petVisible}
            onSetPetEnabled={handlePetEnabledChange}
          />
        ) : route === "memory" ? (
          <MemoryPage assistantName={assistantName} />
        ) : route === "orchestrator" ? (
          <OrchestratorPage
            sessions={sessionList}
            historySessions={orchestratorHistorySessions}
            workbenchTabs={orchestratorConsoleState.tabs}
            activeWorkbenchTabId={orchestratorConsoleState.activeTabId}
            scheduler={orchestratorScheduler}
            messages={activeOrchestratorMessages}
            activeSessionId={activeOrchestratorSessionId}
            activeProjectPath={activeImportedProjectPath}
            draft={orchestratorDraft}
            isSending={isOrchestratorSending}
            historyFilter={orchestratorHistoryFilter}
            onHistoryFilterChange={handleOrchestratorHistoryFilterChange}
            onApplyHistoryFilter={handleApplyOrchestratorHistoryFilter}
            onActivateWorkbenchTab={handleActivateOrchestratorTab}
            onCloseWorkbenchTab={handleCloseOrchestratorTab}
            onCreateBlankTab={handleCreateBlankOrchestratorTab}
            onDraftChange={handleOrchestratorDraftChange}
            onSendMessage={handleSendOrchestratorMessage}
            onActivateSession={handleActivateOrchestratorSession}
            onApprovePlan={handleApproveOrchestratorPlan}
            onRejectPlan={handleRejectOrchestratorPlan}
            onResumeSession={handleResumeOrchestratorSession}
            onCancelSession={handleCancelOrchestrator}
            onCreateSession={handleCreateOrchestratorSession}
            onDeleteSession={handleDeleteOrchestratorSession}
            onSendQuickMessage={handleSendOrchestratorQuickMessage}
            onStopDelegateTask={(payload) =>
              dispatchOrchestratorAction({
                type: "stop_task",
                payload,
              })
            }
            projectRegistry={importedProjectRegistry}
            isUpdatingProjects={isUpdatingProjects}
            projectError={projectControlError}
            tauriSupported={isTauriRuntime()}
            onImportProject={handleImportProjectToOrchestrator}
            onActivateProject={handleActivateOrchestratorProject}
            onRemoveProject={handleRemoveOrchestratorProject}
          />
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
            macConsoleStatus={macConsoleStatus}
            onNavigate={handleNavigate}
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

async function ensureOrchestratorProjectPermission(projectPath: string) {
  try {
    await upsertChatFolderPermission(projectPath, "full_access");
  } catch (error) {
    const detail = error instanceof Error ? error.message : "unknown error";
    throw new Error(`主控项目权限尚未同步到 core，请重新激活或重新导入该项目。${detail ? ` (${detail})` : ""}`);
  }
}

async function restoreImportedProjectsToCore(registry: ReturnType<typeof loadImportedProjectRegistry>) {
  const permissionPlan = buildFolderPermissionPlan(registry);
  for (const permission of permissionPlan) {
    await upsertChatFolderPermission(permission.path, permission.access_level);
  }
}

function normalizeAttachedPaths(paths: string[]): string[] {
  const normalized: string[] = [];
  for (const path of paths) {
    const trimmed = path.trim();
    if (!trimmed) {
      continue;
    }
    const normalizedPath = normalizeProjectPath(trimmed);
    if (!normalized.includes(normalizedPath)) {
      normalized.push(normalizedPath);
    }
  }
  return normalized;
}

function mergeUniquePaths(current: string[], incoming: string[]): string[] {
  const merged = [...current];
  for (const path of incoming) {
    if (!merged.includes(path)) {
      merged.push(path);
    }
  }
  return merged;
}

function buildChatAttachments(
  folders: string[],
  files: string[],
  images: string[],
): ChatAttachment[] {
  return [
    ...folders.map((path) => ({ type: "folder" as const, path })),
    ...files.map((path) => ({ type: "file" as const, path })),
    ...images.map((path) => ({ type: "image" as const, path })),
  ];
}

function resolveParentDirectory(path: string): string | null {
  const normalized = normalizeProjectPath(path);
  const slashIndex = Math.max(normalized.lastIndexOf("/"), normalized.lastIndexOf("\\"));
  if (slashIndex <= 0) {
    return null;
  }
  const parent = normalized.slice(0, slashIndex);
  return parent ? normalizeProjectPath(parent) : null;
}

function resolveRoute(hash: string): AppRoute {
  if (hash === "#/chat") return "chat";
  if (hash === "#/persona") return "persona";
  if (hash === "#/memory") return "memory";
  if (hash === "#/history") return "overview";
  if (hash === "#/tools") return "tools";
  if (hash === "#/capabilities") return "capabilities";
  if (hash === "#/orchestrator") return "orchestrator";
  return "overview";
}

function routeToHash(route: AppRoute): string {
  if (route === "chat") return "#/chat";
  if (route === "persona") return "#/persona";
  if (route === "memory") return "#/memory";
  if (route === "tools") return "#/tools";
  if (route === "capabilities") return "#/capabilities";
  if (route === "orchestrator") return "#/orchestrator";
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
  if (focusMode === "orchestrator") {
    return "主控编排";
  }
  return "休眠";
}

function syncMessagesFromRuntime(current: ChatEntry[], incoming: Parameters<typeof mergeMessages>[1]): ChatEntry[] {
  // Runtime payload contains full chat snapshot; empty list means messages were cleared.
  if (!Array.isArray(incoming) || incoming.length === 0) {
    // Keep local in-flight/failed assistant bubbles and unsynced local user input.
    // Also keep just-completed local assistant replies tied to unsynced local users.
    // This avoids transient runtime updates dropping fresh local conversation.
    const unsyncedUserContents = new Set(
      current
        .filter((entry) => entry.role === "user" && entry.id.startsWith("user-"))
        .map((entry) => entry.content),
    );
    return current.filter(
      (entry) =>
        entry.state === "streaming" ||
        entry.state === "failed" ||
        (entry.role === "user" && entry.id.startsWith("user-")) ||
        (entry.role === "assistant" &&
          entry.state == null &&
          Boolean(entry.requestMessage) &&
          unsyncedUserContents.has(entry.requestMessage ?? "")),
    );
  }
  return mergeMessages(current, incoming);
}

function isExplicitOrchestratorEntry(message: string): boolean {
  return /(进入主控|切到主控|开启主控|主控模式)/.test(message);
}

function extractDelegateRequest(task: OrchestratorTask): OrchestratorDelegateRequest {
  const candidate = task.artifacts?.delegate_request as OrchestratorDelegateRequest | undefined;
  if (!candidate || typeof candidate !== "object") {
    throw new Error("当前任务缺少 delegate_request 协议");
  }
  return candidate;
}

function extractDelegatePrompt(
  task: OrchestratorTask,
  request: OrchestratorDelegateRequest,
  session: OrchestratorSession,
): string {
  const prompt = task.artifacts?.delegate_prompt;
  if (typeof prompt === "string" && prompt.trim()) {
    return prompt;
  }

  return [
    "你是小晏主控模式派发出的 Codex delegate。",
    `主控总目标: ${session.goal}`,
    `当前任务: ${task.title}`,
    `项目路径: ${request.project_path}`,
    `允许改动范围: ${request.scope_paths.join(", ") || "."}`,
    `禁止路径: ${request.forbidden_paths.join(", ") || "无"}`,
    `验收命令: ${request.acceptance_commands.join(" | ") || "无"}`,
    "最终输出必须严格符合 JSON Schema，且 changed_files 返回相对项目根路径。",
    "仅在必要时执行命令；command_results 最多保留 8 条。",
    "command_results 中 stdout/stderr 只保留关键片段，每条建议不超过 400 字，超出请写 TRUNCATED。",
    "summary 聚焦结论，不要重复粘贴大段文件内容或命令原文输出。",
  ].join("\n");
}

function resolveDelegateTimeoutSeconds(task: OrchestratorTask): number {
  const requested = DELEGATE_TIMEOUT_SECONDS_BY_KIND[task.kind] ?? DELEGATE_TIMEOUT_SECONDS_FALLBACK;
  return Math.max(DELEGATE_TIMEOUT_SECONDS_MIN, Math.min(DELEGATE_TIMEOUT_SECONDS_MAX, requested));
}

function isRecoverableDelegateCompletionConflict(error: unknown): boolean {
  if (!(error instanceof Error)) {
    return false;
  }
  const message = error.message.toLowerCase();
  if (message.includes("request failed: 409")) {
    return true;
  }
  if (!message.includes("request failed: 400")) {
    return false;
  }
  return (
    message.includes("delegate task is not running")
    || message.includes("delegate run id mismatch")
    || message.includes("task is not running")
  );
}

function isRecoverableDelegateStopConflict(error: unknown): boolean {
  if (!(error instanceof Error)) {
    return false;
  }
  const message = error.message.toLowerCase();
  if (message.includes("request failed: 409")) {
    return true;
  }
  if (!message.includes("request failed: 400")) {
    return false;
  }
  return (
    message.includes("delegate task is not running")
    || message.includes("delegate run id mismatch")
    || message.includes("task is not running")
  );
}

function toOrchestratorSessionListFilters(filter: SessionHistoryFilter): Parameters<typeof fetchOrchestratorSessions>[0] {
  const statuses = filter.status.filter((item) => item.trim().length > 0);
  return {
    status: statuses.length > 0 ? statuses : undefined,
    project: filter.project.trim() || undefined,
    keyword: filter.keyword.trim() || undefined,
    from: normalizeHistoryDateFilter(filter.from),
    to: normalizeHistoryDateFilter(filter.to),
  };
}

function normalizeHistoryDateFilter(value: string): string | undefined {
  const trimmed = value.trim();
  if (!trimmed) {
    return undefined;
  }
  const parsed = new Date(trimmed);
  if (Number.isNaN(parsed.getTime())) {
    return undefined;
  }
  return parsed.toISOString();
}

function isIgnorableLocalStopError(error: unknown): boolean {
  if (!(error instanceof Error)) {
    return false;
  }
  const message = error.message.toLowerCase();
  return (
    message.includes("tauri runtime not detected")
    || message.includes("当前环境不是 tauri 宿主")
    || message.includes("delegate process not found")
    || message.includes("already exited")
  );
}

function upsertOrchestratorSession(
  current: OrchestratorSession[],
  next: OrchestratorSession,
): OrchestratorSession[] {
  const without = current.filter((item) => item.session_id !== next.session_id);
  return [...without, next].sort(
    (a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime(),
  );
}

function normalizeOrchestratorSessions(value: unknown): OrchestratorSession[] {
  return Array.isArray(value) ? value : [];
}

function normalizeOrchestratorScheduler(value: unknown): OrchestratorSchedulerSnapshot {
  if (!value || typeof value !== "object") {
    return defaultOrchestratorScheduler;
  }
  const candidate = value as Partial<OrchestratorSchedulerSnapshot>;
  return {
    max_parallel_sessions:
      typeof candidate.max_parallel_sessions === "number"
        ? candidate.max_parallel_sessions
        : defaultOrchestratorScheduler.max_parallel_sessions,
    running_sessions:
      typeof candidate.running_sessions === "number"
        ? candidate.running_sessions
        : defaultOrchestratorScheduler.running_sessions,
    available_slots:
      typeof candidate.available_slots === "number"
        ? candidate.available_slots
        : defaultOrchestratorScheduler.available_slots,
    queued_sessions:
      typeof candidate.queued_sessions === "number"
        ? candidate.queued_sessions
        : defaultOrchestratorScheduler.queued_sessions,
    active_session_id:
      typeof candidate.active_session_id === "string" || candidate.active_session_id === null
        ? candidate.active_session_id
        : defaultOrchestratorScheduler.active_session_id,
    running_session_ids: Array.isArray(candidate.running_session_ids) ? candidate.running_session_ids : [],
    queued_session_ids: Array.isArray(candidate.queued_session_ids) ? candidate.queued_session_ids : [],
    verification_rollup:
      candidate.verification_rollup && typeof candidate.verification_rollup === "object"
        ? {
            total_sessions:
              typeof candidate.verification_rollup.total_sessions === "number"
                ? candidate.verification_rollup.total_sessions
                : 0,
            passed_sessions:
              typeof candidate.verification_rollup.passed_sessions === "number"
                ? candidate.verification_rollup.passed_sessions
                : 0,
            failed_sessions:
              typeof candidate.verification_rollup.failed_sessions === "number"
                ? candidate.verification_rollup.failed_sessions
                : 0,
            pending_sessions:
              typeof candidate.verification_rollup.pending_sessions === "number"
                ? candidate.verification_rollup.pending_sessions
                : 0,
          }
        : defaultOrchestratorScheduler.verification_rollup,
    policy_note: typeof candidate.policy_note === "string" ? candidate.policy_note : null,
  };
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
