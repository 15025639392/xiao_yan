import { afterEach, describe, expect, test, vi } from "vitest";

import {
  clearOrchestratorMessages,
  fetchConfig,
  fetchGoalAdmissionConfig,
  fetchGoalAdmissionConfigHistory,
  fetchChatModels,
  fetchChatFolderPermissions,
  removeChatFolderPermission,
  rollbackGoalAdmissionConfig,
  resetPersona,
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
});
