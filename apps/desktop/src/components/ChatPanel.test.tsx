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
      isSending={false}
      messages={[
        { id: "1", role: "user", content: "你好" },
        { id: "2", role: "assistant", content: "我在。" },
      ]}
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

test("does not render relationship context panels above the chat input", async () => {
  render(
    <ChatPanel
      draft=""
      focusGoalTitle={null}
      isSending={false}
      messages={[]}
      onDraftChange={vi.fn()}
      onSend={vi.fn()}
    />,
  );

  expect(screen.queryByText("当前相处语境")).toBeNull();
  expect(screen.queryByText("本次回应原则")).toBeNull();
});

test("does not subscribe chat page to removed relationship context updates", async () => {
  render(
    <ChatPanel
      draft=""
      focusGoalTitle={null}
      isSending={false}
      messages={[]}
      onDraftChange={vi.fn()}
      onSend={vi.fn()}
    />,
  );

  await waitFor(() => {
    expect(screen.getByText("自由对话")).toBeInTheDocument();
  });
  expect(subscribeAppRealtime).not.toHaveBeenCalled();
  expect(screen.queryByText("当前相处语境")).toBeNull();
  expect(screen.queryByText("本次回应原则")).toBeNull();
});

test("disables send while sending or when the draft is empty", () => {
  const onSend = vi.fn();

  const { rerender } = render(
    <ChatPanel
      draft=""
      focusGoalTitle={null}
      isSending={false}
      messages={[]}
      onDraftChange={vi.fn()}
      onSend={onSend}
    />,
  );

  expect(screen.getByLabelText("发送")).toBeDisabled();

  rerender(
    <ChatPanel
      draft="你好"
      focusGoalTitle={null}
      isSending={true}
      messages={[]}
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
      isSending={false}
      messages={[]}
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
      isSending={false}
      messages={[]}
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

  expect(onSend).toHaveBeenCalledWith({
    mcpServerIds: ["browser"],
    continuousReasoningEnabled: true,
  });
});

test("sends message on Enter key press", () => {
  const onSend = vi.fn();

  render(
    <ChatPanel
      draft="你好"
      focusGoalTitle={null}
      isSending={false}
      messages={[]}
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
      isSending={false}
      messages={[]}
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
      isSending={true}
      messages={[]}
      onDraftChange={vi.fn()}
      onSend={vi.fn()}
    />,
  );

  // 发送按钮应该处于禁用状态
  expect(screen.getByLabelText("发送")).toBeDisabled();
});

test("renders header without legacy plan progress", () => {
  render(
    <ChatPanel
      draft=""
      focusGoalTitle="整理今天的对话记忆"
      isSending={false}
      messages={[]}
      onDraftChange={vi.fn()}
      onSend={vi.fn()}
    />,
  );

  expect(screen.getByText("整理今天的对话记忆")).toBeInTheDocument();
  expect(screen.queryByText(/今日计划|1\/2|完成/)).toBeNull();
});

test("renders quick actions in empty state", () => {
  render(
    <ChatPanel
      draft=""
      focusGoalTitle={null}
      isSending={false}
      messages={[]}
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
      isSending={false}
      messages={[]}
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
      isSending={false}
      messages={[]}
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

    throw new Error(`unexpected request: ${url} [${method}]`);
  });

  vi.stubGlobal("fetch", fetchMock);

  render(
    <ChatPanel
      draft=""
      focusGoalTitle={null}
      isSending={false}
      messages={[]}
      onDraftChange={vi.fn()}
      onSend={vi.fn()}
    />,
  );

  fireEvent.click(screen.getByRole("button", { name: "⚙️ 对话设置" }));

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

    throw new Error(`unexpected request: ${url} [${method}]`);
  });

  vi.stubGlobal("fetch", fetchMock);

  render(
    <ChatPanel
      draft=""
      focusGoalTitle={null}
      isSending={false}
      messages={[]}
      onDraftChange={vi.fn()}
      onSend={vi.fn()}
    />,
  );

  fireEvent.click(screen.getByRole("button", { name: "⚙️ 对话设置" }));

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

    throw new Error(`unexpected request: ${url} [${method}]`);
  });

  vi.stubGlobal("fetch", fetchMock);

  render(
    <ChatPanel
      draft=""
      focusGoalTitle={null}
      isSending={false}
      messages={[]}
      onDraftChange={vi.fn()}
      onSend={vi.fn()}
    />,
  );

  fireEvent.click(screen.getByRole("button", { name: "⚙️ 对话设置" }));
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

    throw new Error(`unexpected request: ${url} [${method}]`);
  });

  vi.stubGlobal("fetch", fetchMock);

  render(
    <ChatPanel
      draft=""
      focusGoalTitle={null}
      isSending={false}
      messages={[]}
      onDraftChange={vi.fn()}
      onSend={vi.fn()}
    />,
  );

  fireEvent.click(screen.getByRole("button", { name: "⚙️ 对话设置" }));
  await screen.findByText("这里仅显示当前连接状态；详细接入与维护入口已收拢到“外部能力”页面。");

  expect(screen.queryByRole("button", { name: "新增 MCP Server" })).not.toBeInTheDocument();
  expect(screen.queryByLabelText("MCP Server ID")).not.toBeInTheDocument();
  expect(screen.getByText("filesystem")).toBeInTheDocument();
  expect(screen.getByText("默认启用")).toBeInTheDocument();
  expect(screen.queryByText(/timeout:/)).toBeNull();
  expect(screen.getByText(/如需新增、编辑、删除或启停，请前往“外部能力/)).toBeInTheDocument();
  expect(
    fetchMock.mock.calls.some(
      ([input, init]) => String(input).endsWith("/config") && (init?.method ?? "GET") === "PUT",
    ),
  ).toBe(false);
});
