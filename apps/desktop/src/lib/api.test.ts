import { afterEach, describe, expect, test, vi } from "vitest";

import {
  chat,
  createDataBackup,
  fetchDataEnvironmentStatus,
  fetchMemoryTimeline,
  fetchConfig,
  fetchMessages,
  fetchChatModels,
  fetchChatFolderPermissions,
  removeChatFolderPermission,
  resolveApiBaseUrl,
  resetPersona,
  importDataBackup,
  updateDataEnvironmentStatus,
  updateConfig,
  resumeChat,
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

  test("sends request_key for chat and resume requests", async () => {
    const fetchMock = vi.fn(async () =>
      new Response(JSON.stringify({ response_id: "resp_1", assistant_message_id: "assistant_1" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await chat({ message: "你好", request_key: "request_1" });
    await resumeChat({
      message: "继续",
      assistant_message_id: "assistant_1",
      partial_content: "前半句",
      request_key: "request_1",
    });

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      "http://127.0.0.1:8000/chat",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ message: "你好", request_key: "request_1" }),
      }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "http://127.0.0.1:8000/chat/resume",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          message: "继续",
          assistant_message_id: "assistant_1",
          partial_content: "前半句",
          request_key: "request_1",
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
          chat_continuous_reasoning_enabled: true,
          chat_mcp_enabled: true,
          chat_mcp_servers: [
            {
              server_id: "filesystem",
              command: "npx",
              args: ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
              enabled: true,
              timeout_seconds: 20,
            },
          ],
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
    expect(config.chat_continuous_reasoning_enabled).toBe(true);
    expect(config.chat_mcp_enabled).toBe(true);
    expect(config.chat_mcp_servers[0]?.server_id).toBe("filesystem");
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

  test("normalizes updateConfig response when MCP fields are omitted", async () => {
    const fetchMock = vi.fn(async () =>
      new Response(
        JSON.stringify({
          chat_context_limit: 8,
          chat_provider: "openai",
          chat_model: "gpt-5.4-mini",
          chat_read_timeout_seconds: 120,
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    const updated = await updateConfig({ chat_model: "gpt-5.4-mini" });

    expect(updated.chat_context_limit).toBe(8);
    expect(updated.chat_model).toBe("gpt-5.4-mini");
    expect(updated.chat_continuous_reasoning_enabled).toBe(true);
    expect(updated.chat_mcp_enabled).toBe(false);
    expect(updated.chat_mcp_servers).toEqual([]);
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

  test("builds memory timeline query with namespace and search keyword", async () => {
    const fetchMock = vi.fn(async () =>
      new Response(
        JSON.stringify({
          entries: [],
          total_count: 0,
          query_summary: null,
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    await fetchMemoryTimeline({
      limit: 20,
      namespace: "long_term",
      q: "长期偏好",
      visibility: "user",
      status: "active",
    });

    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/memory/timeline?limit=20&status=active&namespace=long_term&visibility=user&q=%E9%95%BF%E6%9C%9F%E5%81%8F%E5%A5%BD",
    );
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
