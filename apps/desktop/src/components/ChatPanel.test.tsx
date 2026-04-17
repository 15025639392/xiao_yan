import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, vi } from "vitest";

const { fetchMemorySummary } = vi.hoisted(() => ({
  fetchMemorySummary: vi.fn(),
}));

const { subscribeAppRealtime } = vi.hoisted(() => ({
  subscribeAppRealtime: vi.fn(),
}));

vi.mock("../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../lib/api")>("../lib/api");
  return {
    ...actual,
    fetchMemorySummary,
  };
});

vi.mock("../lib/realtime", () => ({
  subscribeAppRealtime,
}));

import { ChatPanel } from "./ChatPanel";

beforeEach(() => {
  fetchMemorySummary.mockReset();
  subscribeAppRealtime.mockReset();
  fetchMemorySummary.mockReturnValue(new Promise(() => {}));
  subscribeAppRealtime.mockReturnValue(() => {});
});

test("renders the chat page with header and messages", () => {
  render(
    <ChatPanel
      draft=""
      focusGoalTitle="整理今天的对话记忆"
      focusModeLabel="晨间计划"
      isSending={false}
      messages={[
        { id: "1", role: "user", content: "你好" },
        { id: "2", role: "assistant", content: "我在。" },
      ]}
      modeLabel="运行中"
      onDraftChange={vi.fn()}
      onSend={vi.fn()}
    />,
  );

  // 标题显示当前目标
  expect(screen.getByText("整理今天的对话记忆")).toBeInTheDocument();
  // 消息内容可见
  expect(screen.getByText("你好")).toBeInTheDocument();
  expect(screen.getByText("我在。")).toBeInTheDocument();
  // 发送按钮存在
  expect(screen.getByLabelText("发送")).toBeInTheDocument();
});

test("renders relationship context above the chat input when available", async () => {
  fetchMemorySummary.mockResolvedValue({
    total_estimated: 12,
    by_kind: {},
    recent_count: 2,
    strong_memories: 1,
    relationship: {
      available: true,
      boundaries: ["先直接说判断，不用绕弯"],
      commitments: ["答应你先说风险再给建议"],
      preferences: ["喜欢先听理由再做决定"],
    },
    available: true,
  });

  render(
    <ChatPanel
      draft=""
      focusGoalTitle={null}
      focusModeLabel="常规自主"
      isSending={false}
      messages={[]}
      modeLabel="运行中"
      onDraftChange={vi.fn()}
      onSend={vi.fn()}
    />,
  );

  await waitFor(() => {
    expect(screen.getByText("当前相处语境")).toBeInTheDocument();
  });
  expect(screen.getByText("本次回应原则")).toBeInTheDocument();
  expect(screen.getAllByText("先直接说判断，不用绕弯").length).toBeGreaterThanOrEqual(2);
  expect(screen.getAllByText("答应你先说风险再给建议").length).toBeGreaterThanOrEqual(2);
  expect(screen.getAllByText("喜欢先听理由再做决定").length).toBeGreaterThanOrEqual(2);
});

test("updates relationship context from realtime memory events", async () => {
  fetchMemorySummary.mockResolvedValue({
    total_estimated: 0,
    by_kind: {},
    recent_count: 0,
    strong_memories: 0,
    relationship: {
      available: false,
      boundaries: [],
      commitments: [],
      preferences: [],
    },
    available: true,
  });

  let listener: ((event: any) => void) | null = null;
  subscribeAppRealtime.mockImplementation((callback) => {
    listener = callback;
    return () => {};
  });

  render(
    <ChatPanel
      draft=""
      focusGoalTitle={null}
      focusModeLabel="常规自主"
      isSending={false}
      messages={[]}
      modeLabel="运行中"
      onDraftChange={vi.fn()}
      onSend={vi.fn()}
    />,
  );

  await waitFor(() => {
    expect(subscribeAppRealtime).toHaveBeenCalled();
  });

  await act(async () => {
    listener?.({
      type: "memory_updated",
      payload: {
        summary: {
          total_estimated: 20,
          by_kind: {},
          recent_count: 3,
          strong_memories: 2,
          relationship: {
            available: true,
            boundaries: ["如果我判断错了，希望你直接纠正我"],
            commitments: ["答应你复杂问题不装懂，会先说明不确定性"],
            preferences: ["更喜欢一起推演方案"],
          },
          available: true,
        },
        relationship: {
          available: true,
          boundaries: ["如果我判断错了，希望你直接纠正我"],
          commitments: ["答应你复杂问题不装懂，会先说明不确定性"],
          preferences: ["更喜欢一起推演方案"],
        },
        timeline: [],
      },
    });
  });

  await waitFor(() => {
    expect(screen.getAllByText("如果我判断错了，希望你直接纠正我").length).toBeGreaterThanOrEqual(2);
  });
});

test("disables send while sending or when the draft is empty", () => {
  const onSend = vi.fn();

  const { rerender } = render(
    <ChatPanel
      draft=""
      focusGoalTitle={null}
      focusModeLabel="休眠"
      isSending={false}
      messages={[]}
      modeLabel="休眠中"
      onDraftChange={vi.fn()}
      onSend={onSend}
    />,
  );

  expect(screen.getByLabelText("发送")).toBeDisabled();

  rerender(
    <ChatPanel
      draft="你好"
      focusGoalTitle={null}
      focusModeLabel="休眠"
      isSending={true}
      messages={[]}
      modeLabel="休眠中"
      onDraftChange={vi.fn()}
      onSend={onSend}
    />,
  );

  expect(screen.getByLabelText("发送")).toBeDisabled();
});

test("forwards input changes and send events", () => {
  const onDraftChange = vi.fn();
  const onSend = vi.fn();

  render(
    <ChatPanel
      draft="你好吗"
      focusGoalTitle={null}
      focusModeLabel="常规自主"
      isSending={false}
      messages={[]}
      modeLabel="运行中"
      onDraftChange={onDraftChange}
      onSend={onSend}
    />,
  );

  fireEvent.change(screen.getByLabelText("对话输入"), {
    target: { value: "晚点再聊" },
  });
  fireEvent.click(screen.getByLabelText("发送"));

  expect(onDraftChange).toHaveBeenCalledWith("晚点再聊");
  expect(onSend).toHaveBeenCalledTimes(1);
});

test("sends selected MCP server ids with onSend", async () => {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    const method = init?.method ?? "GET";

    if (url.endsWith("/config") && method === "GET") {
      return new Response(
        JSON.stringify({
          chat_context_limit: 6,
          chat_provider: "openai",
          chat_model: "gpt-5.4",
          chat_read_timeout_seconds: 180,
          chat_mcp_enabled: true,
          chat_mcp_servers: [
            {
              server_id: "filesystem",
              command: "npx",
              args: ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
              enabled: true,
              timeout_seconds: 20,
            },
            {
              server_id: "browser",
              command: "npx",
              args: ["-y", "@modelcontextprotocol/server-browser"],
              enabled: true,
              timeout_seconds: 20,
            },
          ],
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        },
      );
    }

    throw new Error(`unexpected request: ${url} [${method}]`);
  });
  vi.stubGlobal("fetch", fetchMock);

  const onSend = vi.fn();
  render(
    <ChatPanel
      draft="帮我读取项目结构"
      focusGoalTitle={null}
      focusModeLabel="常规自主"
      isSending={false}
      messages={[]}
      modeLabel="运行中"
      onDraftChange={vi.fn()}
      onSend={onSend}
    />,
  );

  fireEvent.click(screen.getByRole("button", { name: "选择 MCP Servers" }));

  await waitFor(() => {
    expect(screen.getByLabelText("MCP Server filesystem")).toBeInTheDocument();
  });

  fireEvent.click(screen.getByLabelText("MCP Server filesystem"));
  fireEvent.click(screen.getByLabelText("发送"));

  expect(onSend).toHaveBeenCalledWith({ mcpServerIds: ["browser"] });
});

test("sends message on Enter key press", () => {
  const onSend = vi.fn();

  render(
    <ChatPanel
      draft="你好"
      focusGoalTitle={null}
      focusModeLabel="常规自主"
      isSending={false}
      messages={[]}
      modeLabel="运行中"
      onDraftChange={vi.fn()}
      onSend={onSend}
    />,
  );

  const textarea = screen.getByLabelText("对话输入");
  fireEvent.keyDown(textarea, { key: "Enter", shiftKey: false });

  expect(onSend).toHaveBeenCalledTimes(1);
});

test("does not send on Shift+Enter", () => {
  const onSend = vi.fn();

  render(
    <ChatPanel
      draft="你好"
      focusGoalTitle={null}
      focusModeLabel="常规自主"
      isSending={false}
      messages={[]}
      modeLabel="运行中"
      onDraftChange={vi.fn()}
      onSend={onSend}
    />,
  );

  const textarea = screen.getByLabelText("对话输入");
  fireEvent.keyDown(textarea, { key: "Enter", shiftKey: true });

  expect(onSend).not.toHaveBeenCalled();
});

test("renders loading state when sending", () => {
  render(
    <ChatPanel
      draft=""
      focusGoalTitle={null}
      focusModeLabel="常规自主"
      isSending={true}
      messages={[]}
      modeLabel="运行中"
      onDraftChange={vi.fn()}
      onSend={vi.fn()}
    />,
  );

  // 发送按钮应该处于禁用状态
  expect(screen.getByLabelText("发送")).toBeDisabled();
});

test("renders today's plan progress in header", () => {
  render(
    <ChatPanel
      draft=""
      focusGoalTitle="整理今天的对话记忆"
      focusModeLabel="常规自主"
      isSending={false}
      messages={[]}
      modeLabel="运行中"
      todayPlan={{
        goal_id: "goal-1",
        goal_title: "整理今天的对话记忆",
        steps: [
          { content: "回顾昨日对话", status: "completed" },
          { content: "整理关键信息", status: "pending" },
        ],
      }}
      onDraftChange={vi.fn()}
      onSend={vi.fn()}
    />,
  );

  // 今日计划进度显示在头部
  expect(screen.getByText(/今日计划.*1\/2.*完成/)).toBeInTheDocument();
});

test("renders quick actions in empty state", () => {
  render(
    <ChatPanel
      draft=""
      focusGoalTitle={null}
      focusModeLabel="常规自主"
      isSending={false}
      messages={[]}
      modeLabel="运行中"
      onDraftChange={vi.fn()}
      onSend={vi.fn()}
    />,
  );

  // 空状态下显示快捷操作按钮
  expect(screen.getByRole("button", { name: "理一理今天" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "陪我捋一捋" })).toBeInTheDocument();
});

test("quick action buttons populate draft", () => {
  const onDraftChange = vi.fn();

  render(
    <ChatPanel
      draft=""
      focusGoalTitle={null}
      focusModeLabel="常规自主"
      isSending={false}
      messages={[]}
      modeLabel="运行中"
      onDraftChange={onDraftChange}
      onSend={vi.fn()}
    />,
  );

  fireEvent.click(screen.getByRole("button", { name: "理一理今天" }));
  expect(onDraftChange).toHaveBeenCalledWith("小晏，陪我理一下今天最该先做的事");
});

test("supports adding and removing attached folders in chat input", () => {
  const onPickFolder = vi.fn();
  const onPickFile = vi.fn();
  const onPickImage = vi.fn();
  const onRemoveAttachedFolder = vi.fn();
  const onRemoveAttachedFile = vi.fn();
  const onRemoveAttachedImage = vi.fn();

  render(
    <ChatPanel
      draft="请帮我看目录结构"
      focusGoalTitle={null}
      focusModeLabel="常规自主"
      isSending={false}
      messages={[]}
      modeLabel="运行中"
      attachedFolders={["/tmp/workspace/project-a"]}
      attachedFiles={["/tmp/workspace/project-a/README.md"]}
      attachedImages={["/tmp/workspace/project-a/screenshot.png"]}
      onDraftChange={vi.fn()}
      onSend={vi.fn()}
      onPickFolder={onPickFolder}
      onPickFile={onPickFile}
      onPickImage={onPickImage}
      onRemoveAttachedFolder={onRemoveAttachedFolder}
      onRemoveAttachedFile={onRemoveAttachedFile}
      onRemoveAttachedImage={onRemoveAttachedImage}
    />,
  );

  fireEvent.click(screen.getByRole("button", { name: "添加文件夹" }));
  fireEvent.click(screen.getByRole("button", { name: "添加文件" }));
  fireEvent.click(screen.getByRole("button", { name: "添加图片" }));
  expect(onPickFolder).toHaveBeenCalledTimes(1);
  expect(onPickFile).toHaveBeenCalledTimes(1);
  expect(onPickImage).toHaveBeenCalledTimes(1);

  expect(screen.getByText("/tmp/workspace/project-a")).toBeInTheDocument();
  expect(screen.getByText("/tmp/workspace/project-a/README.md")).toBeInTheDocument();
  expect(screen.getByText("/tmp/workspace/project-a/screenshot.png")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "移除文件夹 /tmp/workspace/project-a" }));
  fireEvent.click(screen.getByRole("button", { name: "移除文件 /tmp/workspace/project-a/README.md" }));
  fireEvent.click(screen.getByRole("button", { name: "移除图片 /tmp/workspace/project-a/screenshot.png" }));
  expect(onRemoveAttachedFolder).toHaveBeenCalledWith("/tmp/workspace/project-a");
  expect(onRemoveAttachedFile).toHaveBeenCalledWith("/tmp/workspace/project-a/README.md");
  expect(onRemoveAttachedImage).toHaveBeenCalledWith("/tmp/workspace/project-a/screenshot.png");
});

test("updates chat model inside config modal", async () => {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    const method = init?.method ?? "GET";

    if (url.endsWith("/config")) {
      if (method === "GET") {
        return new Response(JSON.stringify({ chat_context_limit: 6, chat_provider: "openai", chat_model: "gpt-5.4", chat_read_timeout_seconds: 180 }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }
      return new Response(JSON.stringify({ chat_context_limit: 6, chat_provider: "openai", chat_model: "gpt-5.4-mini", chat_read_timeout_seconds: 180 }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }

    if (url.endsWith("/config/chat-models")) {
      return new Response(
        JSON.stringify({
          providers: [
            {
              provider_id: "openai",
              provider_name: "OpenAI",
              models: ["gpt-5.4", "gpt-5.4-mini"],
              default_model: "gpt-5.4",
              error: null,
            },
          ],
          current_provider: "openai",
          current_model: "gpt-5.4",
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        },
      );
    }

    if (url.endsWith("/config/data-environment") && method === "GET") {
      return new Response(
        JSON.stringify({
          testing_mode: false,
          mempalace_palace_path: "/tmp/palace",
          mempalace_wing: "wing_xiaoyan",
          mempalace_room: "chat_exchange",
          default_backup_directory: "/tmp/backups",
          switch_backup_path: null,
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        },
      );
    }

    if (url.endsWith("/chat/folder-permissions") && method === "GET") {
      return new Response(JSON.stringify({ permissions: [] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }

    throw new Error(`unexpected request: ${url} [${method}]`);
  });

  vi.stubGlobal("fetch", fetchMock);

  render(
    <ChatPanel
      draft=""
      focusGoalTitle={null}
      focusModeLabel="常规自主"
      isSending={false}
      messages={[]}
      modeLabel="运行中"
      onDraftChange={vi.fn()}
      onSend={vi.fn()}
    />,
  );

  fireEvent.click(screen.getByRole("button", { name: "⚙️ 配置" }));

  const modelSelect = await screen.findByLabelText("聊天模型");
  fireEvent.change(modelSelect, { target: { value: "gpt-5.4-mini" } });

  await waitFor(() => {
    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/config",
      expect.objectContaining({
        method: "PUT",
        body: JSON.stringify({ chat_provider: "openai", chat_model: "gpt-5.4-mini" }),
      }),
    );
  });
});

test("renders config modal above its overlay", async () => {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    const method = init?.method ?? "GET";

    if (url.endsWith("/config") && method === "GET") {
      return new Response(
        JSON.stringify({
          chat_context_limit: 6,
          chat_provider: "openai",
          chat_model: "gpt-5.4",
          chat_read_timeout_seconds: 180,
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        },
      );
    }

    if (url.endsWith("/config/chat-models")) {
      return new Response(
        JSON.stringify({
          providers: [
            {
              provider_id: "openai",
              provider_name: "OpenAI",
              models: ["gpt-5.4"],
              default_model: "gpt-5.4",
              error: null,
            },
          ],
          current_provider: "openai",
          current_model: "gpt-5.4",
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        },
      );
    }

    if (url.endsWith("/config/data-environment") && method === "GET") {
      return new Response(
        JSON.stringify({
          testing_mode: false,
          mempalace_palace_path: "/tmp/palace",
          mempalace_wing: "wing_xiaoyan",
          mempalace_room: "chat_exchange",
          default_backup_directory: "/tmp/backups",
          switch_backup_path: null,
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        },
      );
    }

    if (url.endsWith("/chat/folder-permissions") && method === "GET") {
      return new Response(JSON.stringify({ permissions: [] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }

    throw new Error(`unexpected request: ${url} [${method}]`);
  });

  vi.stubGlobal("fetch", fetchMock);

  render(
    <ChatPanel
      draft=""
      focusGoalTitle={null}
      focusModeLabel="常规自主"
      isSending={false}
      messages={[]}
      modeLabel="运行中"
      onDraftChange={vi.fn()}
      onSend={vi.fn()}
    />,
  );

  fireEvent.click(screen.getByRole("button", { name: "⚙️ 配置" }));

  const dialog = await screen.findByRole("dialog");
  expect(dialog.className).toContain("z-[1001]");

  const overlay = document.querySelector(".config-panel-overlay");
  expect(overlay).not.toBeNull();
  expect(overlay?.className).toContain("z-[1000]");
});

test("updates continuous reasoning switch inside config modal", async () => {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    const method = init?.method ?? "GET";

    if (url.endsWith("/config")) {
      if (method === "GET") {
        return new Response(
          JSON.stringify({
            chat_context_limit: 6,
            chat_provider: "openai",
            chat_model: "gpt-5.4",
            chat_read_timeout_seconds: 180,
            chat_continuous_reasoning_enabled: false,
          }),
          {
            status: 200,
            headers: { "Content-Type": "application/json" },
          },
        );
      }
      expect(method).toBe("PUT");
      expect(init?.body).toBe(JSON.stringify({ chat_continuous_reasoning_enabled: true }));
      return new Response(
        JSON.stringify({
          chat_context_limit: 6,
          chat_provider: "openai",
          chat_model: "gpt-5.4",
          chat_read_timeout_seconds: 180,
          chat_continuous_reasoning_enabled: true,
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        },
      );
    }

    if (url.endsWith("/config/chat-models")) {
      return new Response(
        JSON.stringify({
          providers: [
            {
              provider_id: "openai",
              provider_name: "OpenAI",
              models: ["gpt-5.4", "gpt-5.4-mini"],
              default_model: "gpt-5.4",
              error: null,
            },
          ],
          current_provider: "openai",
          current_model: "gpt-5.4",
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        },
      );
    }

    if (url.endsWith("/config/data-environment") && method === "GET") {
      return new Response(
        JSON.stringify({
          testing_mode: false,
          mempalace_palace_path: "/tmp/palace",
          mempalace_wing: "wing_xiaoyan",
          mempalace_room: "chat_exchange",
          default_backup_directory: "/tmp/backups",
          switch_backup_path: null,
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        },
      );
    }

    if (url.endsWith("/chat/folder-permissions") && method === "GET") {
      return new Response(JSON.stringify({ permissions: [] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }

    throw new Error(`unexpected request: ${url} [${method}]`);
  });

  vi.stubGlobal("fetch", fetchMock);

  render(
    <ChatPanel
      draft=""
      focusGoalTitle={null}
      focusModeLabel="常规自主"
      isSending={false}
      messages={[]}
      modeLabel="运行中"
      onDraftChange={vi.fn()}
      onSend={vi.fn()}
    />,
  );

  fireEvent.click(screen.getByRole("button", { name: "⚙️ 配置" }));
  const toggle = await screen.findByLabelText("启用持续推理");
  fireEvent.click(toggle);

  await waitFor(() => {
    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/config",
      expect.objectContaining({
        method: "PUT",
        body: JSON.stringify({ chat_continuous_reasoning_enabled: true }),
      }),
    );
  });
});

test("shows MCP section as read-only inside config modal", async () => {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    const method = init?.method ?? "GET";

    if (url.endsWith("/config")) {
      if (method === "GET") {
        return new Response(
          JSON.stringify({
            chat_context_limit: 6,
            chat_provider: "openai",
            chat_model: "gpt-5.4",
            chat_read_timeout_seconds: 180,
            chat_mcp_enabled: true,
            chat_mcp_servers: [
              {
                server_id: "filesystem",
                command: "npx",
                args: ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
                cwd: null,
                env: {},
                enabled: true,
                timeout_seconds: 20,
              },
            ],
          }),
          {
            status: 200,
            headers: { "Content-Type": "application/json" },
          },
        );
      }
      throw new Error("should not update MCP config in read-only modal");
    }

    if (url.endsWith("/config/chat-models")) {
      return new Response(
        JSON.stringify({
          providers: [
            {
              provider_id: "openai",
              provider_name: "OpenAI",
              models: ["gpt-5.4", "gpt-5.4-mini"],
              default_model: "gpt-5.4",
              error: null,
            },
          ],
          current_provider: "openai",
          current_model: "gpt-5.4",
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        },
      );
    }

    if (url.endsWith("/config/data-environment") && method === "GET") {
      return new Response(
        JSON.stringify({
          testing_mode: false,
          mempalace_palace_path: "/tmp/palace",
          mempalace_wing: "wing_xiaoyan",
          mempalace_room: "chat_exchange",
          default_backup_directory: "/tmp/backups",
          switch_backup_path: null,
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        },
      );
    }

    if (url.endsWith("/chat/folder-permissions") && method === "GET") {
      return new Response(JSON.stringify({ permissions: [] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }

    throw new Error(`unexpected request: ${url} [${method}]`);
  });

  vi.stubGlobal("fetch", fetchMock);

  render(
    <ChatPanel
      draft=""
      focusGoalTitle={null}
      focusModeLabel="常规自主"
      isSending={false}
      messages={[]}
      modeLabel="运行中"
      onDraftChange={vi.fn()}
      onSend={vi.fn()}
    />,
  );

  fireEvent.click(screen.getByRole("button", { name: "⚙️ 配置" }));
  await screen.findByText("MCP 管理入口已迁移到工具箱，此处仅展示当前状态与配置快照。");

  expect(screen.queryByRole("button", { name: "新增 MCP Server" })).not.toBeInTheDocument();
  expect(screen.queryByLabelText("MCP Server ID")).not.toBeInTheDocument();
  expect(screen.getByText("filesystem")).toBeInTheDocument();
  expect(screen.getByText(/如需新增、编辑、删除或启停，请前往“工具箱/)).toBeInTheDocument();
  expect(
    fetchMock.mock.calls.some(
      ([input, init]) => String(input).endsWith("/config") && (init?.method ?? "GET") === "PUT",
    ),
  ).toBe(false);
});
