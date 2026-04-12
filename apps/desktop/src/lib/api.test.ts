import { afterEach, describe, expect, test, vi } from "vitest";

import {
  chat,
  clearOrchestratorMessages,
  createDataBackup,
  deleteOrchestratorSession,
  fetchDataEnvironmentStatus,
  fetchConfig,
  fetchOrchestratorSessions,
  fetchMessages,
  fetchGoalAdmissionConfig,
  fetchGoalAdmissionConfigHistory,
  fetchChatModels,
  fetchChatFolderPermissions,
  removeChatFolderPermission,
  rollbackGoalAdmissionConfig,
  runOrchestratorConsoleCommand,
  resolveApiBaseUrl,
  resetPersona,
  stopOrchestratorDelegate,
  importDataBackup,
  updateDataEnvironmentStatus,
  updateConfig,
  updateGoalAdmissionConfig,
  upsertChatFolderPermission,
  updatePersona,
  updatePersonaFeatures,
  updatePersonality,
  updateSpeakingStyle,
} from "./api";

describe("persona api methods", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  test("uses PUT for persona update endpoints and POST for reset", async () => {
    const fetchMock = vi.fn(async () =>
      new Response(JSON.stringify({ success: true, profile: {} }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await updatePersona({ name: "小晏" });
    await updatePersonality({ openness: 80 });
    await updateSpeakingStyle({ response_length: "short" });
    await updatePersonaFeatures({ avatar_enabled: true });
    await resetPersona();

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      "http://127.0.0.1:8000/persona",
      expect.objectContaining({ method: "PUT" }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "http://127.0.0.1:8000/persona/personality",
      expect.objectContaining({ method: "PUT" }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      3,
      "http://127.0.0.1:8000/persona/speaking-style",
      expect.objectContaining({ method: "PUT" }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      4,
      "http://127.0.0.1:8000/persona/features",
      expect.objectContaining({ method: "PUT" }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      5,
      "http://127.0.0.1:8000/persona/reset",
      expect.objectContaining({ method: "POST" }),
    );
  });

  test("uses chat folder permissions endpoints with expected methods", async () => {
    const fetchMock = vi.fn(async () =>
      new Response(JSON.stringify({ permissions: [] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await fetchChatFolderPermissions();
    await upsertChatFolderPermission("/tmp/project", "read_only");
    await removeChatFolderPermission("/tmp/project");

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      "http://127.0.0.1:8000/chat/folder-permissions",
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "http://127.0.0.1:8000/chat/folder-permissions",
      expect.objectContaining({
        method: "PUT",
        body: JSON.stringify({
          path: "/tmp/project",
          access_level: "read_only",
        }),
      }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      3,
      "http://127.0.0.1:8000/chat/folder-permissions?path=%2Ftmp%2Fproject",
      expect.objectContaining({ method: "DELETE" }),
    );
  });

  test("clears orchestrator messages with DELETE endpoint", async () => {
    const fetchMock = vi.fn(async () =>
      new Response(
        JSON.stringify({
          session_id: "session-1",
          deleted_count: 3,
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    const payload = await clearOrchestratorMessages("session-1");

    expect(payload).toEqual({
      session_id: "session-1",
      deleted_count: 3,
    });
    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/orchestrator/sessions/session-1/messages",
      expect.objectContaining({ method: "DELETE" }),
    );
  });

  test("deletes orchestrator session with DELETE endpoint", async () => {
    const fetchMock = vi.fn(async () =>
      new Response(
        JSON.stringify({
          session_id: "session-1",
          deleted: true,
          cleared_messages: 5,
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    const payload = await deleteOrchestratorSession("session-1");

    expect(payload).toEqual({
      session_id: "session-1",
      deleted: true,
      cleared_messages: 5,
    });
    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/orchestrator/sessions/session-1",
      expect.objectContaining({ method: "DELETE" }),
    );
  });

  test("fetches orchestrator sessions with filters", async () => {
    const fetchMock = vi.fn(async () =>
      new Response(JSON.stringify([]), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await fetchOrchestratorSessions({
      status: ["running", "failed"],
      project: "demo-project",
      from: "2026-04-08T00:00:00.000Z",
      to: "2026-04-09T00:00:00.000Z",
      keyword: "主控",
    });

    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/orchestrator/sessions?status=running&status=failed&project=demo-project&from=2026-04-08T00%3A00%3A00.000Z&to=2026-04-09T00%3A00%3A00.000Z&keyword=%E4%B8%BB%E6%8E%A7",
    );
  });

  test("stops a delegate task through orchestrator stop endpoint", async () => {
    const fetchMock = vi.fn(async () =>
      new Response(
        JSON.stringify({
          session_id: "session-1",
          project_path: "/tmp/demo-project",
          project_name: "demo-project",
          goal: "demo",
          status: "failed",
          delegates: [],
          entered_at: "2026-04-08T12:00:00.000Z",
          updated_at: "2026-04-08T12:10:00.000Z",
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    await stopOrchestratorDelegate({
      session_id: "session-1",
      task_id: "task-1",
      delegate_run_id: "run-1",
      reason: "manual stop",
    });

    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/orchestrator/delegates/stop",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          session_id: "session-1",
          task_id: "task-1",
          delegate_run_id: "run-1",
          reason: "manual stop",
        }),
      }),
    );
  });

  test("runs orchestrator console command through unified endpoint", async () => {
    const fetchMock = vi.fn(async () =>
      new Response(
        JSON.stringify({
          session: {
            session_id: "session-1",
            project_path: "/tmp/demo-project",
            project_name: "demo-project",
            goal: "demo",
            status: "running",
            delegates: [],
            entered_at: "2026-04-08T12:00:00.000Z",
            updated_at: "2026-04-08T12:10:00.000Z",
          },
          assistant_message_id: "assistant-console-1",
          created_session: true,
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    await runOrchestratorConsoleCommand({
      message: "进入主控后先总结当前进展",
      project_path: "/tmp/demo-project",
    });

    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/orchestrator/console/command",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          message: "进入主控后先总结当前进展",
          project_path: "/tmp/demo-project",
        }),
      }),
    );
  });

  test("updates chat config with chat_model", async () => {
    const fetchMock = vi.fn(async () =>
      new Response(
        JSON.stringify({
          chat_context_limit: 6,
          chat_provider: "openai",
          chat_model: "gpt-5.4-mini",
          chat_read_timeout_seconds: 180,
          providers: [
            {
              provider_id: "openai",
              provider_name: "OpenAI",
              models: ["gpt-5.4-mini"],
              default_model: "gpt-5.4-mini",
              error: null,
            },
          ],
          current_provider: "openai",
          current_model: "gpt-5.4-mini",
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    const config = await fetchConfig();
    expect(config.chat_model).toBe("gpt-5.4-mini");
    expect(config.chat_provider).toBe("openai");
    const models = await fetchChatModels();
    expect(models.providers[0]?.models).toContain("gpt-5.4-mini");

    await updateConfig({ chat_model: "gpt-5.4" });
    expect(fetchMock).toHaveBeenNthCalledWith(
      3,
      "http://127.0.0.1:8000/config",
      expect.objectContaining({
        method: "PUT",
        body: JSON.stringify({
          chat_model: "gpt-5.4",
        }),
      }),
    );
  });

  test("uses goal-admission config endpoints with expected methods", async () => {
    const fetchMock = vi.fn(async () =>
      new Response(
        JSON.stringify({
          stability_warning_rate: 0.6,
          stability_danger_rate: 0.35,
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    await fetchGoalAdmissionConfig();
    await updateGoalAdmissionConfig({ stability_warning_rate: 0.7 });
    await fetchGoalAdmissionConfigHistory(5);
    await rollbackGoalAdmissionConfig();

    expect(fetchMock).toHaveBeenNthCalledWith(1, "http://127.0.0.1:8000/config/goal-admission");
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "http://127.0.0.1:8000/config/goal-admission",
      expect.objectContaining({
        method: "PUT",
        body: JSON.stringify({
          stability_warning_rate: 0.7,
        }),
      }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      3,
      "http://127.0.0.1:8000/config/goal-admission/history?limit=5",
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      4,
      "http://127.0.0.1:8000/config/goal-admission/rollback",
      expect.objectContaining({
        method: "POST",
      }),
    );
  });

  test("uses data environment backup endpoints with expected methods", async () => {
    const fetchMock = vi.fn(async () =>
      new Response(
        JSON.stringify({
          testing_mode: false,
          mempalace_palace_path: "/tmp/palace",
          mempalace_wing: "wing_xiaoyan",
          mempalace_room: "chat_exchange",
          default_backup_directory: "/tmp/backups",
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    await fetchDataEnvironmentStatus();
    await updateDataEnvironmentStatus({ testing_mode: true, backup_before_switch: true });
    await createDataBackup({ backup_path: "/tmp/backups/custom.zip" });
    await importDataBackup({ backup_path: "/tmp/backups/custom.zip", make_pre_import_backup: true });

    expect(fetchMock).toHaveBeenNthCalledWith(1, "http://127.0.0.1:8000/config/data-environment");
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "http://127.0.0.1:8000/config/data-environment",
      expect.objectContaining({
        method: "PUT",
        body: JSON.stringify({ testing_mode: true, backup_before_switch: true }),
      }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      3,
      "http://127.0.0.1:8000/config/data-backup",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ backup_path: "/tmp/backups/custom.zip" }),
      }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      4,
      "http://127.0.0.1:8000/config/data-backup/import",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ backup_path: "/tmp/backups/custom.zip", make_pre_import_backup: true }),
      }),
    );
  });

  test("resolves API base url with fallback and normalization", () => {
    expect(resolveApiBaseUrl(undefined)).toBe("http://127.0.0.1:8000");
    expect(resolveApiBaseUrl("https://api.example.com/")).toBe("https://api.example.com");
    expect(resolveApiBaseUrl("  https://api.example.com/v1//  ")).toBe("https://api.example.com/v1");
    expect(resolveApiBaseUrl("   ")).toBe("http://127.0.0.1:8000");
  });

  test("fetches chat messages with pagination query params", async () => {
    const fetchMock = vi.fn(async () =>
      new Response(
        JSON.stringify({
          messages: [],
          has_more: true,
          next_offset: 80,
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    await fetchMessages({ limit: 80, offset: 0 });

    expect(fetchMock).toHaveBeenCalledWith("http://127.0.0.1:8000/messages?limit=80&offset=0");
  });

  test("sends chat attachments payload when provided", async () => {
    const fetchMock = vi.fn(async () =>
      new Response(
        JSON.stringify({
          response_id: "resp_1",
          assistant_message_id: "assistant_1",
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    await chat({
      message: "看一下附件",
      attachments: [
        { type: "file", path: "/tmp/readme.md" },
        { type: "image", path: "/tmp/screenshot.png" },
      ],
    });

    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/chat",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          message: "看一下附件",
          attachments: [
            { type: "file", path: "/tmp/readme.md" },
            { type: "image", path: "/tmp/screenshot.png" },
          ],
        }),
      }),
    );
  });
});
