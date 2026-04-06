import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { vi } from "vitest";

import { ChatPanel } from "./ChatPanel";

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
  expect(screen.getByRole("button", { name: "制定今日计划" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "总结对话" })).toBeInTheDocument();
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

  fireEvent.click(screen.getByRole("button", { name: "制定今日计划" }));
  expect(onDraftChange).toHaveBeenCalledWith("帮我制定今天的计划");
});

test("manages folder permission inside config modal via system folder picker", async () => {
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

    if (url.endsWith("/chat/folder-permissions") && method === "GET") {
      return new Response(JSON.stringify({ permissions: [] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }

    if (url.endsWith("/chat/folder-permissions") && method === "PUT") {
      const body = JSON.parse(String(init?.body ?? "{}")) as {
        path: string;
        access_level: "read_only" | "full_access";
      };
      return new Response(
        JSON.stringify({
          permissions: [
            {
              path: body.path,
              access_level: body.access_level,
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

  await waitFor(() => {
    expect(fetchMock).toHaveBeenCalledWith("http://127.0.0.1:8000/config");
    expect(fetchMock).toHaveBeenCalledWith("http://127.0.0.1:8000/chat/folder-permissions");
    expect(fetchMock).toHaveBeenCalledWith("http://127.0.0.1:8000/config/chat-models");
  });

  fireEvent.click(screen.getByRole("button", { name: "选择文件夹" }));
  const pickerInput = screen.getByLabelText("系统文件夹选择器");
  const pickedFile = Object.assign(new File(["demo"], "demo.txt"), {
    path: "/tmp/my-workspace/demo.txt",
    webkitRelativePath: "my-workspace/demo.txt",
  });
  fireEvent.change(pickerInput, {
    target: { files: [pickedFile] },
  });

  fireEvent.change(screen.getByLabelText("权限级别"), {
    target: { value: "full_access" },
  });
  fireEvent.click(screen.getByRole("button", { name: "添加/更新权限" }));

  await waitFor(() => {
    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/chat/folder-permissions",
      expect.objectContaining({ method: "PUT" }),
    );
  });

  await waitFor(() => {
    const permissionItem = document.querySelector(".config-panel__folder-item");
    expect(permissionItem).toBeTruthy();
    expect(within(permissionItem as HTMLElement).getByText("/tmp/my-workspace")).toBeInTheDocument();
    expect(within(permissionItem as HTMLElement).getByText("可读写")).toBeInTheDocument();
  });
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
  fireEvent.click(screen.getByRole("button", { name: "应用模型" }));

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
