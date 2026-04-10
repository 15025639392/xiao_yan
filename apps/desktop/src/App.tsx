import { useEffect, useRef, useState } from "react";
import { invoke } from "@tauri-apps/api/core";

import { ChatPanel } from "./components/ChatPanel";
import type { ChatEntry } from "./components/ChatPanel";
import { PersonaPanel } from "./components/PersonaPanel";
import { ToolPanel } from "./components/ToolPanel";
import type {
  BeingState,
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
  chatWithOrchestrator,
  clearOrchestratorMessages,
  completeOrchestratorDelegate,
  createOrchestratorSession,
  fetchOrchestratorMessages,
  fetchOrchestratorScheduler,
  fetchOrchestratorSessions,
  fetchGoals,
  fetchAutobio,
  fetchMessages,
  fetchState,
  fetchWorld,
  generateOrchestratorPlan,
  rejectOrchestratorPlan,
  removeChatFolderPermission,
  resumeOrchestratorSession,
  resumeChat,
  sleep,
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
import { MemoryPage } from "./pages/MemoryPage";
import { HistoryPage } from "./pages/HistoryPage";
import { CapabilitiesPage } from "./pages/CapabilitiesPage";
import { OrchestratorPage } from "./pages/OrchestratorPage";
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
import { runCodexDelegate } from "./lib/tauri/codexDelegate";
import {
  fsClearAllowedDirectory,
  fsSetAllowedDirectory,
  isTauriRuntime,
  pickDirectory,
} from "./lib/tauri";
import {
  appendOrchestratorDelta,
  finalizeOrchestratorMessage,
  markOrchestratorMessageFailed,
  mergeOrchestratorMessages,
  upsertOrchestratorStreamingMessage,
} from "./lib/orchestratorMessages";

type AppRoute =
  | "overview"
  | "chat"
  | "persona"
  | "memory"
  | "history"
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

export default function App() {
  const [route, setRoute] = useState<AppRoute>(() => resolveRoute(window.location.hash));
  const [state, setState] = useState<BeingState>(initialState);
  const [world, setWorld] = useState<InnerWorldState | null>(null);
  const [macConsoleStatus, setMacConsoleStatus] = useState<MacConsoleBootstrapStatus | null>(null);
  const [autobioEntries, setAutobioEntries] = useState<string[]>([]);
  const [messages, setMessages] = useState<ChatEntry[]>([]);
  const [goals, setGoals] = useState<Goal[]>([]);
  const [orchestratorSessions, setOrchestratorSessions] = useState<OrchestratorSession[]>([]);
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
  const [orchestratorDraft, setOrchestratorDraft] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [isOrchestratorSending, setIsOrchestratorSending] = useState(false);
  const [error, setError] = useState("");
  const [theme, setTheme] = useState<"dark" | "light">(() => loadThemePreference());
  const [showBrandMenu, setShowBrandMenu] = useState(false);
  const [showAbout, setShowAbout] = useState(false);
  const [petVisible, setPetVisible] = useState(false);
  const pendingRequestMessageRef = useRef<string | null>(null);
  const schedulerTickInFlightRef = useRef(false);
  const delegateRunIdsRef = useRef(new Set<string>());
  const orchestratorFeedbackPollInFlightRef = useRef(false);
  const hasAttemptedImportedProjectRestoreRef = useRef(false);
  const focusGoalTitle = resolveFocusGoalTitle(state, goals);
  const assistantName = persona?.name?.trim() || "小晏";
  const assistantIdentity = persona?.identity?.trim() || "AI Agent Desktop";
  const sessionList = normalizeOrchestratorSessions(orchestratorSessions);
  const activeOrchestratorSessionId = state.orchestrator_session?.session_id ?? sessionList[0]?.session_id ?? null;
  const activeOrchestratorMessages =
    activeOrchestratorSessionId == null ? [] : orchestratorMessagesBySession[activeOrchestratorSessionId] ?? [];
  const activeImportedProjectPath = importedProjectRegistry.active_project_path;

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
        const [
          nextState,
          nextMessages,
          nextGoals,
          nextWorld,
          nextAutobio,
          nextOrchestratorSessions,
          nextOrchestratorScheduler,
        ] = await Promise.all([
          fetchState(),
          fetchMessages(),
          fetchGoals(),
          fetchWorld(),
          fetchAutobio(),
          fetchOrchestratorSessions().catch(() => []),
          fetchOrchestratorScheduler().catch(() => defaultOrchestratorScheduler),
        ]);

        if (cancelled) {
          return;
        }

        setState(nextState);
        setMessages((current) => syncMessagesFromRuntime(current, nextMessages.messages));
        setGoals(nextGoals.goals);
        setWorld(nextWorld);
        setAutobioEntries(nextAutobio.entries);
        setOrchestratorSessions(normalizeOrchestratorSessions(nextOrchestratorSessions));
        setOrchestratorScheduler(normalizeOrchestratorScheduler(nextOrchestratorScheduler));
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

  useEffect(() => {
    if (state.focus_mode === "orchestrator" && state.orchestrator_session && route !== "orchestrator") {
      handleNavigate("orchestrator");
    }
  }, [route, state.focus_mode, state.orchestrator_session]);

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
      const runningTask = session.plan.tasks.find(
        (task) => task.status === "running" && typeof task.delegate_run_id === "string" && task.delegate_run_id.length > 0,
      );
      if (!runningTask?.delegate_run_id) {
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
  }, [sessionList]);

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

    setError("");
    setDraft("");
    setIsSending(true);

    try {
      if (isExplicitOrchestratorEntry(content)) {
        if (!activeImportedProjectPath) {
          throw new Error("进入主控前需要先在主控工作台导入并激活一个项目");
        }

        await ensureOrchestratorProjectPermission(activeImportedProjectPath);
        const session = await createOrchestratorSession({
          goal: content,
          project_path: activeImportedProjectPath,
        });
        await generateOrchestratorPlan(session.session_id);
        await Promise.all([
          refreshRuntimeState(),
          refreshOrchestratorSessions(),
          refreshOrchestratorScheduler(),
          refreshOrchestratorMessages(session.session_id),
        ]);
        handleNavigate("orchestrator");
        return;
      }

      const userMessage: ChatEntry = {
        id: `user-${Date.now()}`,
        role: "user",
        content,
      };

      setMessages((current) => [...current, userMessage]);
      pendingRequestMessageRef.current = content;
      await chat(content);
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

  async function refreshRuntimeState() {
    const refreshedState = await fetchState();
    setState(refreshedState);
  }

  async function handlePersonaUpdated() {
    try {
      const [nextState, nextMessages, nextGoals, nextWorld, nextAutobio] = await Promise.all([
        fetchState(),
        fetchMessages(),
        fetchGoals(),
        fetchWorld(),
        fetchAutobio(),
      ]);

      setState(nextState);
      setMessages(syncMessagesFromRuntime([], nextMessages.messages));
      setGoals(nextGoals.goals);
      setWorld(nextWorld);
      setAutobioEntries(nextAutobio.entries);
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "同步失败");
    }
  }

  async function refreshOrchestratorSessions() {
    setOrchestratorSessions(normalizeOrchestratorSessions(await fetchOrchestratorSessions()));
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

  function handleClearOrchestratorConsole() {
    const sessionId = activeOrchestratorSessionId;
    if (!sessionId) {
      return;
    }

    void (async () => {
      try {
        setError("");
        await clearOrchestratorMessages(sessionId);
        setOrchestratorMessagesBySession((current) => ({
          ...current,
          [sessionId]: [],
        }));
      } catch (err) {
        setError(err instanceof Error ? err.message : "清空主控控制台失败");
      }
    })();
  }

  async function sendOrchestratorMessage(
    content: string,
    options: { clearDraft: boolean },
  ): Promise<void> {
    const sessionId = activeOrchestratorSessionId;
    if (!sessionId || !content) {
      return;
    }

    setError("");
    if (options.clearDraft) {
      setOrchestratorDraft("");
    }
    setIsOrchestratorSending(true);

    try {
      await chatWithOrchestrator(sessionId, content);
      await Promise.all([
        refreshOrchestratorSessions(),
        refreshOrchestratorScheduler(),
        refreshOrchestratorMessages(sessionId),
      ]);
    } catch (err) {
      if (options.clearDraft) {
        setOrchestratorDraft(content);
      }
      setError(err instanceof Error ? err.message : "主控消息发送失败");
    } finally {
      setIsOrchestratorSending(false);
    }
  }

  async function handleSendOrchestratorMessage() {
    await sendOrchestratorMessage(orchestratorDraft.trim(), { clearDraft: true });
  }

  async function handleSendOrchestratorQuickMessage(message: string) {
    await sendOrchestratorMessage(message.trim(), { clearDraft: false });
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
          <button
            className={`app-sidebar__nav-item ${route === "orchestrator" ? "app-sidebar__nav-item--active" : ""}`}
            onClick={() => handleNavigate("orchestrator")}
            type="button"
          >
            <svg className="app-sidebar__nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M4 6h16M4 12h10M4 18h7" />
              <path d="M17 9l3 3-3 3" />
            </svg>
            <span>主控工作台</span>
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
        ) : route === "history" ? (
          <HistoryPage onSelectRollback={handleRollback} />
        ) : route === "orchestrator" ? (
          <OrchestratorPage
            sessions={sessionList}
            scheduler={orchestratorScheduler}
            messages={activeOrchestratorMessages}
            activeSessionId={activeOrchestratorSessionId}
            activeProjectPath={activeImportedProjectPath}
            draft={orchestratorDraft}
            isSending={isOrchestratorSending}
            onDraftChange={setOrchestratorDraft}
            onSendMessage={handleSendOrchestratorMessage}
            onActivateSession={handleActivateOrchestratorSession}
            onApprovePlan={handleApproveOrchestratorPlan}
            onRejectPlan={handleRejectOrchestratorPlan}
            onResumeSession={handleResumeOrchestratorSession}
            onCancelSession={handleCancelOrchestrator}
            onSendQuickMessage={handleSendOrchestratorQuickMessage}
            onClearConsole={handleClearOrchestratorConsole}
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

function resolveRoute(hash: string): AppRoute {
  if (hash === "#/chat") return "chat";
  if (hash === "#/persona") return "persona";
  if (hash === "#/memory") return "memory";
  if (hash === "#/history") return "history";
  if (hash === "#/tools") return "tools";
  if (hash === "#/capabilities") return "capabilities";
  if (hash === "#/orchestrator") return "orchestrator";
  return "overview";
}

function routeToHash(route: AppRoute): string {
  if (route === "chat") return "#/chat";
  if (route === "persona") return "#/persona";
  if (route === "memory") return "#/memory";
  if (route === "history") return "#/history";
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
  if (focusMode === "self_programming") {
    return "自我编程";
  }
  if (focusMode === "orchestrator") {
    return "主控编排";
  }
  return "休眠";
}

function syncMessagesFromRuntime(current: ChatEntry[], incoming: Parameters<typeof mergeMessages>[1]): ChatEntry[] {
  // Runtime payload contains full chat snapshot; empty list means messages were cleared.
  if (!Array.isArray(incoming) || incoming.length === 0) {
    // Keep local in-flight/failed assistant bubbles to avoid interrupting retry UX.
    return current.filter((entry) => entry.state === "streaming" || entry.state === "failed");
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
  if (!message.includes("request failed: 409")) {
    return false;
  }
  return true;
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
