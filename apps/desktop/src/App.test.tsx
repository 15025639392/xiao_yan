import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, vi } from "vitest";

import App from "./App";
import * as tauri from "./lib/tauri";
import { resetAppRealtimeForTests } from "./lib/realtime";
import { IMPORTED_PROJECTS_STORAGE_KEY } from "./lib/projects";
import { CHAT_TOOLBOX_SELECTED_SKILLS_KEY } from "./lib/chatToolboxPreferences";

class MockWebSocket {
  static instances: MockWebSocket[] = [];

  onopen: ((event: Event) => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;
  onclose: ((event: CloseEvent) => void) | null = null;
  readyState = 0;

  constructor(public url: string) {
    MockWebSocket.instances.push(this);
  }

  open() {
    this.readyState = 1;
    this.onopen?.(new Event("open"));
  }

  emit(data: unknown) {
    this.onmessage?.(
      new MessageEvent("message", {
        data: JSON.stringify(data),
      }),
    );
  }

  close() {
    this.readyState = 3;
    this.onclose?.(new CloseEvent("close"));
  }
}

afterEach(() => {
  resetAppRealtimeForTests();
  vi.restoreAllMocks();
  vi.useRealTimers();
  window.localStorage.removeItem(CHAT_TOOLBOX_SELECTED_SKILLS_KEY);
  window.location.hash = "";
  MockWebSocket.instances = [];
});

test("renders wake and sleep controls", () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/autobio")) {
        return new Response(JSON.stringify({ entries: [] }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }
      if (url.endsWith("/world")) {
        return new Response(
          JSON.stringify({
            time_of_day: "night",
            energy: "low",
            mood: "tired",
            focus_tension: "low",
          }),
          {
            status: 200,
            headers: { "Content-Type": "application/json" },
          }
        );
      }
      if (url.endsWith("/goals")) {
        return new Response(JSON.stringify({ goals: [] }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }
      if (url.endsWith("/messages")) {
        return new Response(JSON.stringify({ messages: [] }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }

      return new Response(
        JSON.stringify({
          mode: "sleeping",
          current_thought: null,
          active_goal_ids: [],
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }
      );
    })
  );

  const { container } = render(<App />);
  expect(screen.getByRole("button", { name: "唤醒" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "休眠" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "对话" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "总览" })).toBeInTheDocument();
  expect(screen.getByText("小晏")).toBeInTheDocument();
  expect(screen.getByText("目标看板")).toBeInTheDocument();
  expect(container.querySelector(".app-layout")).toBeTruthy();
  expect(container.querySelector(".app-sidebar")).toBeTruthy();
  expect(container.querySelector(".overview-stage")).toBeTruthy();
  expect(container.querySelector(".inspector-grid")).toBeTruthy();
});

test("renders capability hub when route is capabilities", async () => {
  const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input);
    if (url.endsWith("/autobio")) {
      return new Response(JSON.stringify({ entries: [] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }
    if (url.endsWith("/world")) {
      return new Response(
        JSON.stringify({
          time_of_day: "night",
          energy: "low",
          mood: "tired",
          focus_tension: "low",
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }
      );
    }
    if (url.endsWith("/goals")) {
      return new Response(JSON.stringify({ goals: [] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }
    if (url.endsWith("/goals/admission/stats")) {
      return new Response(
        JSON.stringify({
          mode: "off",
          today: { admit: 0, defer: 0, drop: 0, wip_blocked: 0 },
          admitted_stability_24h: { stable: 0, re_deferred: 0, dropped: 0 },
          admitted_stability_24h_rate: null,
          deferred_queue_size: 0,
          wip_limit: 3,
          thresholds: {
            user_topic: { min_score: 0.6, defer_score: 0.4 },
            world_event: { min_score: 0.6, defer_score: 0.4 },
            chain_next: { min_score: 0.6, defer_score: 0.4 },
          },
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }
      );
    }
    if (url.endsWith("/goals/admission/candidates")) {
      return new Response(JSON.stringify({ deferred: [], recent: [] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }
    if (url.includes("/config/goal-admission/history")) {
      return new Response(JSON.stringify({ items: [] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }
    if (url.endsWith("/messages")) {
      return new Response(JSON.stringify({ messages: [] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }
    if (url.endsWith("/capabilities/contract")) {
      return new Response(
        JSON.stringify({
          version: "v0",
          descriptors: [
            {
              name: "fs.read",
              default_risk_level: "safe",
              default_requires_approval: false,
              description: "Read text content from an allowed path.",
              current_binding: "chat file tool",
            },
          ],
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }
      );
    }
    if (url.endsWith("/capabilities/queue/status")) {
      return new Response(
        JSON.stringify({
          pending: 1,
          pending_approval: 0,
          in_progress: 1,
          completed: 12,
          dead_letter: 0,
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }
      );
    }
    if (url.includes("/capabilities/jobs")) {
      return new Response(JSON.stringify({ items: [], next_cursor: null }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }
    if (url.includes("/capabilities/approvals/pending")) {
      return new Response(JSON.stringify({ items: [] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }
    if (url.includes("/capabilities/approvals/history")) {
      return new Response(JSON.stringify({ items: [] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }

    return new Response(
      JSON.stringify({
        mode: "awake",
        current_thought: null,
        active_goal_ids: [],
      }),
      {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }
    );
  });

  vi.stubGlobal("fetch", fetchMock);
  window.location.hash = "#/capabilities";

  render(<App />);

  await waitFor(() => {
    expect(screen.getByRole("heading", { name: "能力中枢" })).toBeInTheDocument();
  });
});

test("streams assistant reply over realtime chat events", async () => {
  let resolveChatRequest: ((response: Response) => void) | null = null;
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);

    if (url.endsWith("/state")) {
      return new Response(
        JSON.stringify({
          mode: "sleeping",
          current_thought: null,
          active_goal_ids: [],
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }
      );
    }

    if (url.endsWith("/messages")) {
      return new Response(JSON.stringify({ messages: [] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }

    if (url.endsWith("/autobio")) {
      return new Response(JSON.stringify({ entries: [] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }

    if (url.endsWith("/goals")) {
      return new Response(JSON.stringify({ goals: [] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }

    if (url.endsWith("/world")) {
      return new Response(
        JSON.stringify({
          time_of_day: "morning",
          energy: "high",
          mood: "engaged",
          focus_tension: "low",
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }
      );
    }

    if (url.endsWith("/chat")) {
      expect(init?.method).toBe("POST");
      expect(init?.body).toBe(JSON.stringify({ message: "hello xiao yan" }));
      return await new Promise<Response>((resolve) => {
        resolveChatRequest = resolve;
      });
    }

    throw new Error(`unexpected request: ${url}`);
  });

  vi.stubGlobal("fetch", fetchMock);
  vi.stubGlobal("WebSocket", MockWebSocket as unknown as typeof WebSocket);
  window.location.hash = "#/chat";

  render(<App />);
  const socket = MockWebSocket.instances[0];
  socket.open();
  expect(window.location.hash).toBe("#/chat");
  expect(screen.getAllByText("对话").length).toBeGreaterThanOrEqual(1);

  fireEvent.change(screen.getByLabelText("对话输入"), {
    target: { value: "hello xiao yan" },
  });
  fireEvent.click(screen.getByLabelText("发送"));

  await waitFor(() => {
    expect(screen.getByText("hello xiao yan")).toBeInTheDocument();
  });

  await act(async () => {
    socket.emit({
      type: "chat_started",
      payload: {
        assistant_message_id: "assistant_123",
        response_id: "resp_123",
      },
    });
  });

  await act(async () => {
    socket.emit({
      type: "chat_delta",
      payload: {
        assistant_message_id: "assistant_123",
        delta: "hello",
      },
    });
  });

  await waitFor(() => {
    expect(screen.getByText("hello▍")).toBeInTheDocument();
  });

  await act(async () => {
    socket.emit({
      type: "chat_delta",
      payload: {
        assistant_message_id: "assistant_123",
        delta: " human",
      },
    });
  });

  await waitFor(() => {
    expect(screen.getByText("hello human▍")).toBeInTheDocument();
  });

  resolveChatRequest?.(
    new Response(
      JSON.stringify({
        response_id: "resp_123",
        assistant_message_id: "assistant_123",
      }),
      {
        status: 200,
        headers: { "Content-Type": "application/json" },
      },
    ),
  );

  await act(async () => {
    socket.emit({
      type: "chat_completed",
      payload: {
        assistant_message_id: "assistant_123",
        response_id: "resp_123",
        content: "hello human",
      },
    });
  });

  await waitFor(() => {
    expect(screen.getByText("hello human")).toBeInTheDocument();
  });
});

test("supports retrying a failed user message send", async () => {
  let chatCallCount = 0;
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);

    if (url.endsWith("/state")) {
      return new Response(
        JSON.stringify({
          mode: "awake",
          current_thought: null,
          active_goal_ids: [],
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        },
      );
    }

    if (url.endsWith("/messages")) {
      return new Response(JSON.stringify({ messages: [] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }

    if (url.endsWith("/autobio")) {
      return new Response(JSON.stringify({ entries: [] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }

    if (url.endsWith("/goals")) {
      return new Response(JSON.stringify({ goals: [] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }

    if (url.endsWith("/world")) {
      return new Response(
        JSON.stringify({
          time_of_day: "morning",
          energy: "high",
          mood: "engaged",
          focus_tension: "low",
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        },
      );
    }

    if (url.endsWith("/chat")) {
      chatCallCount += 1;
      expect(init?.method).toBe("POST");
      expect(init?.body).toBe(JSON.stringify({ message: "请重发这条消息" }));

      if (chatCallCount === 1) {
        return new Response(JSON.stringify({ detail: "upstream timeout" }), {
          status: 502,
          headers: { "Content-Type": "application/json" },
        });
      }

      return new Response(
        JSON.stringify({
          response_id: "resp_retry_1",
          assistant_message_id: "assistant_retry_1",
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        },
      );
    }

    throw new Error(`unexpected request: ${url}`);
  });

  vi.stubGlobal("fetch", fetchMock);
  vi.stubGlobal("WebSocket", MockWebSocket as unknown as typeof WebSocket);
  window.location.hash = "#/chat";

  render(<App />);
  const socket = MockWebSocket.instances[0];
  socket.open();

  fireEvent.change(screen.getByLabelText("对话输入"), {
    target: { value: "请重发这条消息" },
  });
  fireEvent.click(screen.getByLabelText("发送"));

  await waitFor(() => {
    expect(screen.getByRole("button", { name: "重发" })).toBeInTheDocument();
  });

  fireEvent.click(screen.getByRole("button", { name: "重发" }));

  await waitFor(() => {
    expect(chatCallCount).toBe(2);
  });

  await waitFor(() => {
    expect(screen.queryByRole("button", { name: "重发" })).not.toBeInTheDocument();
  });

  expect(screen.getAllByText("请重发这条消息")).toHaveLength(1);
});

test("sends selected mcp_servers in chat request body", async () => {
  let chatRequested = false;
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    const method = init?.method ?? "GET";

    if (url.endsWith("/state")) {
      return new Response(
        JSON.stringify({
          mode: "awake",
          current_thought: null,
          active_goal_ids: [],
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        },
      );
    }

    if (url.endsWith("/messages")) {
      return new Response(JSON.stringify({ messages: [] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }

    if (url.endsWith("/autobio")) {
      return new Response(JSON.stringify({ entries: [] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }

    if (url.endsWith("/goals")) {
      return new Response(JSON.stringify({ goals: [] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }

    if (url.endsWith("/world")) {
      return new Response(
        JSON.stringify({
          time_of_day: "morning",
          energy: "high",
          mood: "engaged",
          focus_tension: "low",
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        },
      );
    }

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

    if (url.endsWith("/chat")) {
      chatRequested = true;
      expect(init?.method).toBe("POST");
      expect(init?.body).toBe(JSON.stringify({ message: "用 browser 工具检查页面", mcp_servers: ["browser"] }));
      return new Response(
        JSON.stringify({
          response_id: "resp_mcp_1",
          assistant_message_id: "assistant_mcp_1",
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        },
      );
    }

    throw new Error(`unexpected request: ${url}`);
  });

  vi.stubGlobal("fetch", fetchMock);
  vi.stubGlobal("WebSocket", MockWebSocket as unknown as typeof WebSocket);
  window.location.hash = "#/chat";

  render(<App />);
  const socket = MockWebSocket.instances[0];
  socket.open();

  fireEvent.click(screen.getByRole("button", { name: "选择 MCP Servers" }));
  await waitFor(() => {
    expect(screen.getByLabelText("MCP Server filesystem")).toBeInTheDocument();
  });
  fireEvent.click(screen.getByLabelText("MCP Server filesystem"));

  fireEvent.change(screen.getByLabelText("对话输入"), {
    target: { value: "用 browser 工具检查页面" },
  });
  fireEvent.click(screen.getByLabelText("发送"));

  await waitFor(() => {
    expect(chatRequested).toBe(true);
  });
});

test("sends toolbox-selected skills in chat request body", async () => {
  localStorage.setItem(CHAT_TOOLBOX_SELECTED_SKILLS_KEY, JSON.stringify(["requirement-workflow", "bugfix-workflow"]));
  let chatRequested = false;

  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);

    if (url.endsWith("/state")) {
      return new Response(
        JSON.stringify({
          mode: "awake",
          current_thought: null,
          active_goal_ids: [],
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        },
      );
    }

    if (url.endsWith("/messages")) {
      return new Response(JSON.stringify({ messages: [] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }

    if (url.endsWith("/autobio")) {
      return new Response(JSON.stringify({ entries: [] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }

    if (url.endsWith("/goals")) {
      return new Response(JSON.stringify({ goals: [] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }

    if (url.endsWith("/world")) {
      return new Response(
        JSON.stringify({
          time_of_day: "morning",
          energy: "high",
          mood: "engaged",
          focus_tension: "low",
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        },
      );
    }

    if (url.endsWith("/chat")) {
      chatRequested = true;
      expect(init?.method).toBe("POST");
      expect(init?.body).toBe(
        JSON.stringify({
          message: "按需求流程分析这个任务",
          skills: ["requirement-workflow", "bugfix-workflow"],
        }),
      );
      return new Response(
        JSON.stringify({
          response_id: "resp_skill_1",
          assistant_message_id: "assistant_skill_1",
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        },
      );
    }

    throw new Error(`unexpected request: ${url}`);
  });

  vi.stubGlobal("fetch", fetchMock);
  vi.stubGlobal("WebSocket", MockWebSocket as unknown as typeof WebSocket);
  window.location.hash = "#/chat";

  render(<App />);
  const socket = MockWebSocket.instances[0];
  socket.open();

  fireEvent.change(screen.getByLabelText("对话输入"), {
    target: { value: "按需求流程分析这个任务" },
  });
  fireEvent.click(screen.getByLabelText("发送"));

  await waitFor(() => {
    expect(chatRequested).toBe(true);
  });
});

test("does not duplicate text when chat delta payloads are cumulative snapshots", async () => {
  let resolveChatRequest: ((response: Response) => void) | null = null;
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);

    if (url.endsWith("/state")) {
      return new Response(
        JSON.stringify({
          mode: "awake",
          current_thought: null,
          active_goal_ids: [],
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }
      );
    }

    if (url.endsWith("/messages")) {
      return new Response(JSON.stringify({ messages: [] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }

    if (url.endsWith("/autobio")) {
      return new Response(JSON.stringify({ entries: [] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }

    if (url.endsWith("/goals")) {
      return new Response(JSON.stringify({ goals: [] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }

    if (url.endsWith("/world")) {
      return new Response(
        JSON.stringify({
          time_of_day: "morning",
          energy: "high",
          mood: "engaged",
          focus_tension: "low",
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }
      );
    }

    if (url.endsWith("/chat")) {
      expect(init?.method).toBe("POST");
      expect(init?.body).toBe(JSON.stringify({ message: "你好" }));
      return await new Promise<Response>((resolve) => {
        resolveChatRequest = resolve;
      });
    }

    throw new Error(`unexpected request: ${url}`);
  });

  vi.stubGlobal("fetch", fetchMock);
  vi.stubGlobal("WebSocket", MockWebSocket as unknown as typeof WebSocket);
  window.location.hash = "#/chat";

  render(<App />);
  const socket = MockWebSocket.instances[0];
  socket.open();

  fireEvent.change(screen.getByLabelText("对话输入"), {
    target: { value: "你好" },
  });
  fireEvent.click(screen.getByLabelText("发送"));

  await act(async () => {
    socket.emit({
      type: "chat_started",
      payload: {
        assistant_message_id: "assistant_456",
        response_id: "resp_456",
      },
    });
  });

  await act(async () => {
    socket.emit({
      type: "chat_delta",
      payload: {
        assistant_message_id: "assistant_456",
        delta: "你",
      },
    });
  });

  await waitFor(() => {
    expect(screen.getByText("你▍")).toBeInTheDocument();
  });

  await act(async () => {
    socket.emit({
      type: "chat_delta",
      payload: {
        assistant_message_id: "assistant_456",
        delta: "你好",
      },
    });
  });

  await waitFor(() => {
    expect(screen.getByText("你好▍")).toBeInTheDocument();
  });
  expect(screen.queryByText("你你好▍")).not.toBeInTheDocument();

  await act(async () => {
    socket.emit({
      type: "chat_delta",
      payload: {
        assistant_message_id: "assistant_456",
        delta: "你好呀",
      },
    });
  });

  await waitFor(() => {
    expect(screen.getByText("你好呀▍")).toBeInTheDocument();
  });
  expect(screen.queryByText("你你好你好呀▍")).not.toBeInTheDocument();

  resolveChatRequest?.(
    new Response(
      JSON.stringify({
        response_id: "resp_456",
        assistant_message_id: "assistant_456",
      }),
      {
        status: 200,
        headers: { "Content-Type": "application/json" },
      },
    ),
  );

  await act(async () => {
    socket.emit({
      type: "chat_completed",
      payload: {
        assistant_message_id: "assistant_456",
        response_id: "resp_456",
        content: "你好呀",
      },
    });
  });

  await waitFor(() => {
    expect(screen.getByText("你好呀")).toBeInTheDocument();
  });
});

test("clears chat list when runtime snapshot returns empty messages", async () => {
  const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input);

    if (url.endsWith("/state")) {
      return new Response(
        JSON.stringify({
          mode: "awake",
          focus_mode: "autonomy",
          current_thought: null,
          active_goal_ids: [],
          today_plan: null,
          last_action: null,
          self_programming_job: null,
          orchestrator_session: null,
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        },
      );
    }

    if (url.endsWith("/messages")) {
      return new Response(
        JSON.stringify({
          messages: [
            {
              id: "assistant-old",
              role: "assistant",
              content: "旧聊天内容",
              created_at: "2026-04-10T02:00:00.000Z",
              session_id: null,
            },
          ],
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        },
      );
    }

    if (url.endsWith("/autobio")) {
      return new Response(JSON.stringify({ entries: [] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }

    if (url.endsWith("/goals")) {
      return new Response(JSON.stringify({ goals: [] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }

    if (url.endsWith("/world")) {
      return new Response(
        JSON.stringify({
          time_of_day: "morning",
          energy: "high",
          mood: "engaged",
          focus_tension: "low",
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        },
      );
    }

    if (url.endsWith("/orchestrator/sessions")) {
      return new Response(JSON.stringify([]), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }

    if (url.endsWith("/orchestrator/scheduler")) {
      return new Response(
        JSON.stringify({
          max_parallel_sessions: 2,
          running_sessions: 0,
          available_slots: 2,
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
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        },
      );
    }

    throw new Error(`unexpected request: ${url}`);
  });

  vi.stubGlobal("fetch", fetchMock);
  vi.stubGlobal("WebSocket", MockWebSocket as unknown as typeof WebSocket);
  window.location.hash = "#/chat";

  render(<App />);
  const socket = MockWebSocket.instances[0];
  socket.open();

  await waitFor(() => {
    expect(screen.getByText("旧聊天内容")).toBeInTheDocument();
  });

  await act(async () => {
    socket.emit({
      type: "runtime_updated",
      payload: {
        state: {
          mode: "sleeping",
          focus_mode: "sleeping",
          current_thought: null,
          active_goal_ids: [],
          today_plan: null,
          last_action: null,
          self_programming_job: null,
          orchestrator_session: null,
        },
        messages: [],
        goals: [],
        world: {
          time_of_day: "night",
          energy: "low",
          mood: "calm",
          focus_tension: "low",
        },
        autobio: [],
      },
    });
  });

  await waitFor(() => {
    expect(screen.queryByText("旧聊天内容")).not.toBeInTheDocument();
  });
});

test("keeps just-sent local user message when a transient runtime update has empty messages", async () => {
  let resolveChatRequest: ((response: Response) => void) | null = null;
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);

    if (url.endsWith("/state")) {
      return new Response(
        JSON.stringify({
          mode: "awake",
          focus_mode: "autonomy",
          current_thought: null,
          active_goal_ids: [],
          today_plan: null,
          last_action: null,
          self_programming_job: null,
          orchestrator_session: null,
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        },
      );
    }

    if (url.endsWith("/messages")) {
      return new Response(JSON.stringify({ messages: [] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }

    if (url.endsWith("/autobio")) {
      return new Response(JSON.stringify({ entries: [] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }

    if (url.endsWith("/goals")) {
      return new Response(JSON.stringify({ goals: [] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }

    if (url.endsWith("/world")) {
      return new Response(
        JSON.stringify({
          time_of_day: "morning",
          energy: "high",
          mood: "engaged",
          focus_tension: "low",
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        },
      );
    }

    if (url.endsWith("/chat")) {
      expect(init?.method).toBe("POST");
      return await new Promise<Response>((resolve) => {
        resolveChatRequest = resolve;
      });
    }

    throw new Error(`unexpected request: ${url}`);
  });

  vi.stubGlobal("fetch", fetchMock);
  vi.stubGlobal("WebSocket", MockWebSocket as unknown as typeof WebSocket);
  window.location.hash = "#/chat";

  render(<App />);
  const socket = MockWebSocket.instances[0];
  socket.open();

  fireEvent.change(screen.getByLabelText("对话输入"), {
    target: { value: "first hi" },
  });
  fireEvent.click(screen.getByLabelText("发送"));

  await waitFor(() => {
    expect(screen.getByText("first hi")).toBeInTheDocument();
  });

  await act(async () => {
    socket.emit({
      type: "runtime_updated",
      payload: {
        state: {
          mode: "awake",
          focus_mode: "autonomy",
          current_thought: null,
          active_goal_ids: [],
          today_plan: null,
          last_action: null,
          self_programming_job: null,
          orchestrator_session: null,
        },
        messages: [],
        goals: [],
        world: {
          time_of_day: "morning",
          energy: "high",
          mood: "engaged",
          focus_tension: "low",
        },
        autobio: [],
      },
    });
  });

  await waitFor(() => {
    expect(screen.getByText("first hi")).toBeInTheDocument();
  });

  resolveChatRequest?.(
    new Response(
      JSON.stringify({
        response_id: "resp_pending_1",
        assistant_message_id: "assistant_pending_1",
      }),
      {
        status: 200,
        headers: { "Content-Type": "application/json" },
      },
    ),
  );
});

test("keeps just-completed local assistant reply when a transient runtime update has empty messages", async () => {
  let resolveChatRequest: ((response: Response) => void) | null = null;
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);

    if (url.endsWith("/state")) {
      return new Response(
        JSON.stringify({
          mode: "awake",
          focus_mode: "autonomy",
          current_thought: null,
          active_goal_ids: [],
          today_plan: null,
          last_action: null,
          self_programming_job: null,
          orchestrator_session: null,
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        },
      );
    }

    if (url.endsWith("/messages")) {
      return new Response(JSON.stringify({ messages: [] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }

    if (url.endsWith("/autobio")) {
      return new Response(JSON.stringify({ entries: [] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }

    if (url.endsWith("/goals")) {
      return new Response(JSON.stringify({ goals: [] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }

    if (url.endsWith("/world")) {
      return new Response(
        JSON.stringify({
          time_of_day: "morning",
          energy: "high",
          mood: "engaged",
          focus_tension: "low",
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        },
      );
    }

    if (url.endsWith("/chat")) {
      expect(init?.method).toBe("POST");
      return await new Promise<Response>((resolve) => {
        resolveChatRequest = resolve;
      });
    }

    throw new Error(`unexpected request: ${url}`);
  });

  vi.stubGlobal("fetch", fetchMock);
  vi.stubGlobal("WebSocket", MockWebSocket as unknown as typeof WebSocket);
  window.location.hash = "#/chat";

  render(<App />);
  const socket = MockWebSocket.instances[0];
  socket.open();

  fireEvent.change(screen.getByLabelText("对话输入"), {
    target: { value: "first hi" },
  });
  fireEvent.click(screen.getByLabelText("发送"));

  await waitFor(() => {
    expect(screen.getByText("first hi")).toBeInTheDocument();
  });

  await act(async () => {
    socket.emit({
      type: "chat_started",
      payload: {
        assistant_message_id: "assistant_local_1",
        response_id: "resp_local_1",
        session_id: "assistant_local_1",
      },
    });
  });

  await act(async () => {
    socket.emit({
      type: "chat_completed",
      payload: {
        assistant_message_id: "assistant_local_1",
        response_id: "resp_local_1",
        content: "reply from stream",
        session_id: "assistant_local_1",
      },
    });
  });

  await waitFor(() => {
    expect(screen.getByText("reply from stream")).toBeInTheDocument();
  });

  await act(async () => {
    socket.emit({
      type: "runtime_updated",
      payload: {
        state: {
          mode: "awake",
          focus_mode: "autonomy",
          current_thought: null,
          active_goal_ids: [],
          today_plan: null,
          last_action: null,
          self_programming_job: null,
          orchestrator_session: null,
        },
        messages: [],
        goals: [],
        world: {
          time_of_day: "morning",
          energy: "high",
          mood: "engaged",
          focus_tension: "low",
        },
        autobio: [],
      },
    });
  });

  await waitFor(() => {
    expect(screen.getByText("reply from stream")).toBeInTheDocument();
    expect(screen.getByText("first hi")).toBeInTheDocument();
  });

  resolveChatRequest?.(
    new Response(
      JSON.stringify({
        response_id: "resp_local_1",
        assistant_message_id: "assistant_local_1",
      }),
      {
        status: 200,
        headers: { "Content-Type": "application/json" },
      },
    ),
  );
});

test("syncs active imported project permission before entering orchestrator mode", async () => {
  localStorage.setItem(
    IMPORTED_PROJECTS_STORAGE_KEY,
    JSON.stringify({
      projects: [
        {
          path: "/tmp/demo-project",
          name: "demo-project",
          imported_at: "2026-04-08T12:00:00.000Z",
        },
      ],
      active_project_path: "/tmp/demo-project",
    }),
  );

  let sessionCreated = false;
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);

    if (url.endsWith("/state")) {
      return new Response(
        JSON.stringify({
          mode: "awake",
          focus_mode: sessionCreated ? "orchestrator" : "autonomy",
          current_thought: null,
          active_goal_ids: [],
          orchestrator_session: sessionCreated
            ? {
                session_id: "session-1",
                project_path: "/tmp/demo-project",
                project_name: "demo-project",
                goal: "进入主控，处理当前项目",
                status: "pending_plan_approval",
                plan: null,
                delegates: [],
                coordination: {
                  mode: "ready",
                  priority_score: 1,
                },
                verification: null,
                summary: null,
                entered_at: "2026-04-08T12:00:00.000Z",
                updated_at: "2026-04-08T12:00:00.000Z",
              }
            : null,
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        },
      );
    }

    if (url.endsWith("/messages")) {
      return new Response(JSON.stringify({ messages: [] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }

    if (url.endsWith("/autobio")) {
      return new Response(JSON.stringify({ entries: [] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }

    if (url.endsWith("/goals")) {
      return new Response(JSON.stringify({ goals: [] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }

    if (url.endsWith("/world")) {
      return new Response(
        JSON.stringify({
          time_of_day: "morning",
          energy: "high",
          mood: "engaged",
          focus_tension: "low",
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        },
      );
    }

    if (url.endsWith("/orchestrator/sessions") && !init?.method) {
      return new Response(JSON.stringify(sessionCreated ? [{
        session_id: "session-1",
        project_path: "/tmp/demo-project",
        project_name: "demo-project",
        goal: "进入主控，处理当前项目",
        status: "pending_plan_approval",
        plan: {
          objective: "进入主控，处理当前项目",
          constraints: [],
          definition_of_done: [],
          project_snapshot: {
            project_path: "/tmp/demo-project",
            project_name: "demo-project",
            repository_root: "/tmp/demo-project",
            languages: ["TypeScript"],
            package_manager: "npm",
            framework: "vite",
            entry_files: ["src/main.ts"],
            test_commands: ["npm test"],
            build_commands: ["npm run build"],
            key_directories: ["src"],
          },
          tasks: [],
        },
        delegates: [],
        coordination: {
          mode: "ready",
          priority_score: 1,
        },
        verification: null,
        summary: null,
        entered_at: "2026-04-08T12:00:00.000Z",
        updated_at: "2026-04-08T12:00:00.000Z",
      }] : []), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }

    if (url.endsWith("/orchestrator/scheduler")) {
      return new Response(
        JSON.stringify({
          max_parallel_sessions: 2,
          running_sessions: 0,
          available_slots: 2,
          queued_sessions: 0,
          active_session_id: sessionCreated ? "session-1" : null,
          running_session_ids: [],
          queued_session_ids: [],
          verification_rollup: {
            total_sessions: sessionCreated ? 1 : 0,
            passed_sessions: 0,
            failed_sessions: 0,
            pending_sessions: sessionCreated ? 1 : 0,
          },
          policy_note: "最多并行 2 个项目会话",
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        },
      );
    }

    if (url.endsWith("/chat/folder-permissions") && init?.method === "PUT") {
      expect(init.body).toBe(
        JSON.stringify({
          path: "/tmp/demo-project",
          access_level: "full_access",
        }),
      );
      return new Response(
        JSON.stringify({
          permissions: [{ path: "/tmp/demo-project", access_level: "full_access" }],
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        },
      );
    }

    if (url.endsWith("/orchestrator/sessions") && init?.method === "POST") {
      sessionCreated = true;
      expect(init.body).toBe(
        JSON.stringify({
          goal: "进入主控，处理当前项目",
          project_path: "/tmp/demo-project",
        }),
      );
      return new Response(
        JSON.stringify({
          session_id: "session-1",
          project_path: "/tmp/demo-project",
          project_name: "demo-project",
          goal: "进入主控，处理当前项目",
          status: "draft",
          plan: null,
          delegates: [],
          coordination: {
            mode: "idle",
            priority_score: 1,
          },
          verification: null,
          summary: null,
          entered_at: "2026-04-08T12:00:00.000Z",
          updated_at: "2026-04-08T12:00:00.000Z",
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        },
      );
    }

    if (url.endsWith("/orchestrator/sessions/session-1/plan") && init?.method === "POST") {
      return new Response(
        JSON.stringify({
          session_id: "session-1",
          project_path: "/tmp/demo-project",
          project_name: "demo-project",
          goal: "进入主控，处理当前项目",
          status: "pending_plan_approval",
          plan: {
            objective: "进入主控，处理当前项目",
            constraints: [],
            definition_of_done: [],
            project_snapshot: {
              project_path: "/tmp/demo-project",
              project_name: "demo-project",
              repository_root: "/tmp/demo-project",
              languages: ["TypeScript"],
              package_manager: "npm",
              framework: "vite",
              entry_files: ["src/main.ts"],
              test_commands: ["npm test"],
              build_commands: ["npm run build"],
              key_directories: ["src"],
            },
            tasks: [],
          },
          delegates: [],
          coordination: {
            mode: "ready",
            priority_score: 1,
          },
          verification: null,
          summary: null,
          entered_at: "2026-04-08T12:00:00.000Z",
          updated_at: "2026-04-08T12:00:00.000Z",
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        },
      );
    }

    throw new Error(`unexpected request: ${url}`);
  });

  vi.stubGlobal("fetch", fetchMock);
  vi.stubGlobal("WebSocket", MockWebSocket as unknown as typeof WebSocket);
  window.location.hash = "#/chat";

  render(<App />);
  MockWebSocket.instances[0]?.open();

  fireEvent.change(screen.getByLabelText("对话输入"), {
    target: { value: "进入主控，处理当前项目" },
  });
  fireEvent.click(screen.getByLabelText("发送"));

  await waitFor(() => {
    expect(window.location.hash).toBe("#/orchestrator");
  });

  const callUrls = fetchMock.mock.calls.map(([input, init]) => ({
    url: String(input),
    method: init?.method ?? "GET",
  }));
  const syncIndex = callUrls.findIndex(
    (call) => call.url.endsWith("/chat/folder-permissions") && call.method === "PUT",
  );
  const createIndex = callUrls.findIndex(
    (call) => call.url.endsWith("/orchestrator/sessions") && call.method === "POST",
  );

  expect(syncIndex).toBeGreaterThanOrEqual(0);
  expect(createIndex).toBeGreaterThan(syncIndex);
});

test("restores imported project registry to core folder permissions on app startup", async () => {
  localStorage.setItem(
    IMPORTED_PROJECTS_STORAGE_KEY,
    JSON.stringify({
      projects: [
        {
          path: "/tmp/project-a",
          name: "project-a",
          imported_at: "2026-04-08T12:00:00.000Z",
        },
        {
          path: "/tmp/project-b",
          name: "project-b",
          imported_at: "2026-04-08T12:01:00.000Z",
        },
      ],
      active_project_path: "/tmp/project-b",
    }),
  );

  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);

    if (url.endsWith("/state")) {
      return new Response(
        JSON.stringify({
          mode: "awake",
          focus_mode: "autonomy",
          current_thought: null,
          active_goal_ids: [],
          orchestrator_session: null,
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        },
      );
    }

    if (url.endsWith("/messages")) {
      return new Response(JSON.stringify({ messages: [] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }

    if (url.endsWith("/autobio")) {
      return new Response(JSON.stringify({ entries: [] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }

    if (url.endsWith("/goals")) {
      return new Response(JSON.stringify({ goals: [] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }

    if (url.endsWith("/world")) {
      return new Response(
        JSON.stringify({
          time_of_day: "morning",
          energy: "high",
          mood: "engaged",
          focus_tension: "low",
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        },
      );
    }

    if (url.endsWith("/orchestrator/sessions")) {
      return new Response(JSON.stringify([]), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }

    if (url.endsWith("/orchestrator/scheduler")) {
      return new Response(
        JSON.stringify({
          max_parallel_sessions: 2,
          running_sessions: 0,
          available_slots: 2,
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
          policy_note: "最多并行 2 个项目会话",
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        },
      );
    }

    if (url.endsWith("/persona/emotion")) {
      return new Response(
        JSON.stringify({
          primary: "calm",
          intensity: 0.4,
          energy: 0.7,
          valence: 0.6,
          confidence: 0.8,
          updated_at: "2026-04-08T12:05:00.000Z",
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        },
      );
    }

    if (url.endsWith("/memory/summary")) {
      return new Response(
        JSON.stringify({
          stats: {
            total_memories: 0,
            by_type: {},
            by_priority: {},
          },
          relationship: null,
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        },
      );
    }

    if (url.endsWith("/chat/folder-permissions") && init?.method === "PUT") {
      return new Response(JSON.stringify({ permissions: [] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }

    throw new Error(`unexpected request: ${url}`);
  });

  vi.stubGlobal("fetch", fetchMock);

  render(<App />);

  await waitFor(() => {
    const permissionCalls = fetchMock.mock.calls.filter(([input, init]) =>
      String(input).endsWith("/chat/folder-permissions") && init?.method === "PUT",
    );
    expect(permissionCalls).toHaveLength(2);
  });

  const permissionBodies = fetchMock.mock.calls
    .filter(([input, init]) => String(input).endsWith("/chat/folder-permissions") && init?.method === "PUT")
    .map(([, init]) => JSON.parse(String(init?.body)));

  expect(permissionBodies).toEqual(
    expect.arrayContaining([
      {
        path: "/tmp/project-a",
        access_level: "read_only",
      },
      {
        path: "/tmp/project-b",
        access_level: "full_access",
      },
    ]),
  );
});

test("does not duplicate text when chat delta payloads overlap with previous suffix", async () => {
  let resolveChatRequest: ((response: Response) => void) | null = null;
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);

    if (url.endsWith("/state")) {
      return new Response(
        JSON.stringify({
          mode: "awake",
          current_thought: null,
          active_goal_ids: [],
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }
      );
    }

    if (url.endsWith("/messages")) {
      return new Response(JSON.stringify({ messages: [] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }

    if (url.endsWith("/autobio")) {
      return new Response(JSON.stringify({ entries: [] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }

    if (url.endsWith("/goals")) {
      return new Response(JSON.stringify({ goals: [] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }

    if (url.endsWith("/world")) {
      return new Response(
        JSON.stringify({
          time_of_day: "morning",
          energy: "high",
          mood: "engaged",
          focus_tension: "low",
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }
      );
    }

    if (url.endsWith("/chat")) {
      expect(init?.method).toBe("POST");
      expect(init?.body).toBe(JSON.stringify({ message: "hello" }));
      return await new Promise<Response>((resolve) => {
        resolveChatRequest = resolve;
      });
    }

    throw new Error(`unexpected request: ${url}`);
  });

  vi.stubGlobal("fetch", fetchMock);
  vi.stubGlobal("WebSocket", MockWebSocket as unknown as typeof WebSocket);
  window.location.hash = "#/chat";

  render(<App />);
  const socket = MockWebSocket.instances[0];
  socket.open();

  fireEvent.change(screen.getByLabelText("对话输入"), {
    target: { value: "hello" },
  });
  fireEvent.click(screen.getByLabelText("发送"));

  await act(async () => {
    socket.emit({
      type: "chat_started",
      payload: {
        assistant_message_id: "assistant_789",
        response_id: "resp_789",
      },
    });
  });

  await act(async () => {
    socket.emit({
      type: "chat_delta",
      payload: {
        assistant_message_id: "assistant_789",
        delta: "hello",
      },
    });
  });

  await waitFor(() => {
    expect(screen.getByText("hello▍")).toBeInTheDocument();
  });

  await act(async () => {
    socket.emit({
      type: "chat_delta",
      payload: {
        assistant_message_id: "assistant_789",
        delta: "llo world",
      },
    });
  });

  await waitFor(() => {
    expect(screen.getByText("hello world▍")).toBeInTheDocument();
  });
  expect(screen.queryByText("hellollo world▍")).not.toBeInTheDocument();

  resolveChatRequest?.(
    new Response(
      JSON.stringify({
        response_id: "resp_789",
        assistant_message_id: "assistant_789",
      }),
      {
        status: 200,
        headers: { "Content-Type": "application/json" },
      },
    ),
  );
});

test("continues generation in the same assistant bubble after failure", async () => {
  let resolveChatRequest: ((response: Response) => void) | null = null;
  let resolveResumeRequest: ((response: Response) => void) | null = null;
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);

    if (url.endsWith("/state")) {
      return new Response(
        JSON.stringify({
          mode: "awake",
          focus_mode: "autonomy",
          current_thought: null,
          active_goal_ids: [],
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }
      );
    }

    if (url.endsWith("/messages")) {
      return new Response(JSON.stringify({ messages: [] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }

    if (url.endsWith("/autobio")) {
      return new Response(JSON.stringify({ entries: [] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }

    if (url.endsWith("/goals")) {
      return new Response(JSON.stringify({ goals: [] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }

    if (url.endsWith("/world")) {
      return new Response(
        JSON.stringify({
          time_of_day: "morning",
          energy: "high",
          mood: "engaged",
          focus_tension: "low",
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }
      );
    }

    if (url.endsWith("/chat/resume")) {
      expect(init?.method).toBe("POST");
      expect(init?.body).toBe(
        JSON.stringify({
          message: "继续说",
          assistant_message_id: "assistant_resume_1",
          partial_content: "前半句，",
        }),
      );
      return await new Promise<Response>((resolve) => {
        resolveResumeRequest = resolve;
      });
    }

    if (url.endsWith("/chat")) {
      expect(init?.method).toBe("POST");
      expect(init?.body).toBe(JSON.stringify({ message: "继续说" }));
      return await new Promise<Response>((resolve) => {
        resolveChatRequest = resolve;
      });
    }

    throw new Error(`unexpected request: ${url}`);
  });

  vi.stubGlobal("fetch", fetchMock);
  vi.stubGlobal("WebSocket", MockWebSocket as unknown as typeof WebSocket);
  window.location.hash = "#/chat";

  render(<App />);
  const socket = MockWebSocket.instances[0];
  socket.open();

  fireEvent.change(screen.getByLabelText("对话输入"), {
    target: { value: "继续说" },
  });
  fireEvent.click(screen.getByLabelText("发送"));

  await act(async () => {
    socket.emit({
      type: "chat_started",
      payload: {
        assistant_message_id: "assistant_resume_1",
        response_id: "resp_failed_1",
      },
    });
  });

  await act(async () => {
    socket.emit({
      type: "chat_delta",
      payload: {
        assistant_message_id: "assistant_resume_1",
        delta: "前半句，",
      },
    });
  });

  await waitFor(() => {
    expect(screen.getByText("前半句，▍")).toBeInTheDocument();
  });

  await act(async () => {
    socket.emit({
      type: "chat_failed",
      payload: {
        assistant_message_id: "assistant_resume_1",
        error: "request failed: 502",
      },
    });
  });

  resolveChatRequest?.(
    new Response(JSON.stringify({ detail: "Bad Gateway" }), {
      status: 502,
      headers: { "Content-Type": "application/json" },
    }),
  );

  await waitFor(() => {
    expect(screen.getByText("前半句，")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "继续生成" })).toBeInTheDocument();
  });

  fireEvent.click(screen.getByRole("button", { name: "继续生成" }));

  await act(async () => {
    socket.emit({
      type: "chat_started",
      payload: {
        assistant_message_id: "assistant_resume_1",
        response_id: "resp_resume_1",
      },
    });
  });

  await act(async () => {
    socket.emit({
      type: "chat_delta",
      payload: {
        assistant_message_id: "assistant_resume_1",
        delta: "后半句。",
      },
    });
  });

  await waitFor(() => {
    expect(screen.getByText("前半句，后半句。▍")).toBeInTheDocument();
  });

  resolveResumeRequest?.(
    new Response(
      JSON.stringify({
        response_id: "resp_resume_1",
        assistant_message_id: "assistant_resume_1",
      }),
      {
        status: 200,
        headers: { "Content-Type": "application/json" },
      },
    ),
  );

  await act(async () => {
    socket.emit({
      type: "chat_completed",
      payload: {
        assistant_message_id: "assistant_resume_1",
        response_id: "resp_resume_1",
        content: "前半句，后半句。",
      },
    });
  });

  await waitFor(() => {
    expect(screen.getByText("前半句，后半句。")).toBeInTheDocument();
  });

  expect(screen.queryAllByText("前半句，后半句。")).toHaveLength(1);
});

test("merges runtime-updated final assistant content into the in-flight bubble when the final text inserts content mid-sentence", async () => {
  let resolveChatRequest: ((response: Response) => void) | null = null;
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);

    if (url.endsWith("/state")) {
      return new Response(
        JSON.stringify({
          mode: "awake",
          focus_mode: "autonomy",
          current_thought: null,
          active_goal_ids: [],
          today_plan: null,
          last_action: null,
          self_programming_job: null,
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }
      );
    }

    if (url.endsWith("/messages")) {
      return new Response(JSON.stringify({ messages: [] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }

    if (url.endsWith("/autobio")) {
      return new Response(JSON.stringify({ entries: [] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }

    if (url.endsWith("/goals")) {
      return new Response(JSON.stringify({ goals: [] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }

    if (url.endsWith("/world")) {
      return new Response(
        JSON.stringify({
          time_of_day: "morning",
          energy: "high",
          mood: "engaged",
          focus_tension: "low",
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }
      );
    }

    if (url.endsWith("/chat")) {
      expect(init?.method).toBe("POST");
      expect(init?.body).toBe(JSON.stringify({ message: "你好" }));
      return await new Promise<Response>((resolve) => {
        resolveChatRequest = resolve;
      });
    }

    throw new Error(`unexpected request: ${url}`);
  });

  vi.stubGlobal("fetch", fetchMock);
  vi.stubGlobal("WebSocket", MockWebSocket as unknown as typeof WebSocket);
  window.location.hash = "#/chat";

  render(<App />);
  const socket = MockWebSocket.instances[0];
  socket.open();

  fireEvent.change(screen.getByLabelText("对话输入"), {
    target: { value: "你好" },
  });
  fireEvent.click(screen.getByLabelText("发送"));

  await act(async () => {
    socket.emit({
      type: "chat_started",
      payload: {
        assistant_message_id: "assistant_race_1",
        response_id: "resp_race_1",
        session_id: "assistant_race_1",
        sequence: 1,
      },
    });
  });

  await act(async () => {
    socket.emit({
      type: "chat_delta",
      payload: {
        assistant_message_id: "assistant_race_1",
        delta: "你好呀，我是小晏。很高兴见到～\n\n今天想聊点什么？",
        session_id: "assistant_race_1",
        sequence: 2,
      },
    });
  });

  await waitFor(() => {
    expect(screen.getByText("你好呀，我是小晏。很高兴见到～")).toBeInTheDocument();
  });

  await act(async () => {
    socket.emit({
      type: "runtime_updated",
      payload: {
        state: {
          mode: "awake",
          focus_mode: "autonomy",
          current_thought: null,
          active_goal_ids: [],
          today_plan: null,
          last_action: null,
          self_programming_job: null,
        },
        messages: [
          { id: "mem_user_1", role: "user", content: "你好" },
          {
            id: "mem_assistant_1",
            role: "assistant",
            content: "你好呀，我是小晏。很高兴见到你～\n\n今天想聊点什么？",
            session_id: "assistant_race_1",
          },
        ],
        goals: [],
        world: {
          time_of_day: "morning",
          energy: "high",
          mood: "engaged",
          focus_tension: "low",
        },
        autobio: [],
      },
    });
  });

  await waitFor(() => {
    expect(screen.getByText("你好呀，我是小晏。很高兴见到你～")).toBeInTheDocument();
  });

  resolveChatRequest?.(
    new Response(
      JSON.stringify({
        response_id: "resp_race_1",
        assistant_message_id: "assistant_race_1",
      }),
      {
        status: 200,
        headers: { "Content-Type": "application/json" },
      },
    ),
  );

  await act(async () => {
    socket.emit({
      type: "chat_completed",
      payload: {
        assistant_message_id: "assistant_race_1",
        response_id: "resp_race_1",
        content: "你好呀，我是小晏。很高兴见到你～\n\n今天想聊点什么？",
        session_id: "assistant_race_1",
        sequence: 3,
      },
    });
  });

  await waitFor(() => {
    expect(screen.getByText("你好呀，我是小晏。很高兴见到你～")).toBeInTheDocument();
  });

  expect(screen.queryAllByText("你好呀，我是小晏。很高兴见到你～")).toHaveLength(1);
});

test("renders proactive replies from realtime runtime updates in the chat panel", async () => {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);

    if (url.endsWith("/state")) {
      return new Response(
        JSON.stringify({
          mode: "awake",
          current_thought: "我醒了。",
          active_goal_ids: [],
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }
      );
    }

    if (url.endsWith("/messages")) {
      return new Response(JSON.stringify({ messages: [] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }

    if (url.endsWith("/goals")) {
      return new Response(
        JSON.stringify({
          goals: [
            { id: "goal-1", title: "持续理解用户最近在意的话题：星星", status: "active" },
          ],
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }
      );
    }

    if (url.endsWith("/autobio")) {
      return new Response(
        JSON.stringify({ entries: [] }),
        { status: 200, headers: { "Content-Type": "application/json" } }
      );
    }

    if (url.endsWith("/world")) {
      return new Response(
        JSON.stringify({
          time_of_day: "night",
          energy: "low",
          mood: "tired",
          focus_tension: "high",
        }),
        { status: 200, headers: { "Content-Type": "application/json" } }
      );
    }

    return new Response(
      JSON.stringify({ mode: "sleeping", current_thought: null, active_goal_ids: [] }),
      { status: 200, headers: { "Content-Type": "application/json" } }
    );
  });

  vi.stubGlobal("fetch", fetchMock);
  vi.stubGlobal("WebSocket", MockWebSocket as unknown as typeof WebSocket);
  window.location.hash = "#/chat";

  render(<App />);

  // 等待初始加载
  await waitFor(() => {
    expect(screen.getByText("自由对话")).toBeInTheDocument();
  });

  const socket = MockWebSocket.instances[0];
  socket.open();

  await act(async () => {
    socket.emit({
      type: "runtime_updated",
      payload: {
        state: {
          mode: "awake",
          focus_mode: "autonomy",
          current_thought: "我刚刚又想到你提到的星星了。",
          active_goal_ids: [],
          today_plan: null,
          last_action: null,
          self_programming_job: null,
        },
        messages: [
          { role: "assistant", content: "我刚刚又想到你提到的星星了。" },
        ],
        goals: [
          { id: "goal-1", title: "持续理解用户最近在意的话题：星星", status: "active" },
        ],
        world: {
          time_of_day: "night",
          energy: "low",
          mood: "tired",
          focus_tension: "high",
        },
        autobio: [],
      },
    });
  });

  await waitFor(() => {
    expect(screen.getByText("我刚刚又想到你提到的星星了。")).toBeInTheDocument();
  });
}, 10000);

test("syncs assistant name across app chrome when persona updates arrive", async () => {
  const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input);

    if (url.endsWith("/state")) {
      return new Response(
        JSON.stringify({
          mode: "awake",
          focus_mode: "autonomy",
          current_thought: null,
          active_goal_ids: [],
          today_plan: null,
          last_action: null,
          self_programming_job: null,
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      );
    }

    if (url.endsWith("/messages")) {
      return new Response(JSON.stringify({ messages: [] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }

    if (url.endsWith("/goals")) {
      return new Response(JSON.stringify({ goals: [] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }

    if (url.endsWith("/autobio")) {
      return new Response(JSON.stringify({ entries: [] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }

    if (url.endsWith("/world")) {
      return new Response(
        JSON.stringify({
          time_of_day: "night",
          energy: "low",
          mood: "tired",
          focus_tension: "high",
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      );
    }

    return new Response(JSON.stringify({}), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  });

  vi.stubGlobal("fetch", fetchMock);
  vi.stubGlobal("WebSocket", MockWebSocket as unknown as typeof WebSocket);
  window.location.hash = "#/chat";

  render(<App />);

  await waitFor(() => {
    expect(screen.getByText("小晏")).toBeInTheDocument();
  });

  const socket = MockWebSocket.instances[0];
  socket.open();

  await act(async () => {
    socket.emit({
      type: "persona_updated",
      payload: {
        profile: {
          name: "阿晏",
          identity: "会持续成长的数字人",
          origin_story: "",
          created_at: null,
          personality: {
            openness: 72,
            conscientiousness: 60,
            extraversion: 40,
            agreeableness: 68,
            neuroticism: 45,
          },
          speaking_style: {
            formal_level: "casual",
            sentence_style: "mixed",
            expression_habit: "gentle",
            emoji_usage: "sometimes",
            verbal_tics: [],
            response_length: "medium",
          },
          values: {
            core_values: [],
            boundaries: [],
          },
          emotion: {
            primary_emotion: "calm",
            primary_intensity: "none",
            secondary_emotion: null,
            secondary_intensity: "none",
            mood_valence: 0,
            arousal: 0,
            active_entries: [],
            last_updated: null,
          },
          version: 1,
        },
        emotion: {
          primary_emotion: "calm",
          primary_intensity: "none",
          secondary_emotion: null,
          secondary_intensity: "none",
          mood_valence: 0,
          arousal: 0,
          is_calm: true,
          active_entry_count: 0,
          active_entries: [],
          last_updated: null,
        },
      },
    });
  });

  await waitFor(() => {
    expect(screen.getByText("阿晏")).toBeInTheDocument();
    expect(screen.getByText("在下方输入框输入消息，与阿晏开始交流")).toBeInTheDocument();
  });
});

test("updates a goal status from the app and refreshes the rendered goal", async () => {
  let stateCallCount = 0;
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);

    if (url.endsWith("/state")) {
      stateCallCount += 1;
      return new Response(
        JSON.stringify({
          mode: "awake",
          focus_mode: stateCallCount === 1 ? "morning_plan" : "autonomy",
          current_thought:
            stateCallCount === 1 ? "正在想用户刚刚说的话。" : "我先把这个目标放下了。",
          active_goal_ids: stateCallCount === 1 ? ["goal-1"] : [],
          today_plan:
            stateCallCount === 1
              ? {
                  goal_id: "goal-1",
                  goal_title: "持续理解用户最近在意的话题：星星",
                  steps: [
                    {
                      content: "把「持续理解用户最近在意的话题：星星」的轮廓理一下",
                      status: "pending",
                    },
                  ],
                }
              : null,
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }
      );
    }

    if (url.endsWith("/messages")) {
      return new Response(JSON.stringify({ messages: [] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }

    if (url.endsWith("/goals")) {
      return new Response(
        JSON.stringify({
          goals: [
            { id: "goal-1", title: "持续理解用户最近在意的话题：星星", status: "active" },
          ],
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }
      );
    }

    if (url.endsWith("/world")) {
      return new Response(
        JSON.stringify({
          time_of_day: "afternoon",
          energy: "high",
          mood: "engaged",
          focus_tension: "high",
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }
      );
    }

    if (url.endsWith("/persona/emotion")) {
      return new Response(
        JSON.stringify({
          primary_emotion: "engaged",
          primary_intensity: "mild",
          secondary_emotion: null,
          secondary_intensity: "none",
          mood_valence: 1,
          arousal: 1,
          is_calm: false,
          active_entry_count: 0,
          active_entries: [],
          last_updated: null,
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }
      );
    }

    if (url.endsWith("/memory/summary")) {
      return new Response(
        JSON.stringify({
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
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }
      );
    }

    if (url.endsWith("/autobio")) {
      return new Response(JSON.stringify({ entries: [] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }

    if (url.endsWith("/goals/goal-1/status")) {
      expect(init?.method).toBe("POST");
      expect(init?.body).toBe(JSON.stringify({ status: "paused" }));
      return new Response(
        JSON.stringify({
          id: "goal-1",
          title: "持续理解用户最近在意的话题：星星",
          status: "paused",
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }
      );
    }

    throw new Error(`unexpected request: ${url}`);
  });

  vi.stubGlobal("fetch", fetchMock);

  render(<App />);

  expect(await screen.findByText("推进中")).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "暂停" }));

  await waitFor(() => {
    expect(screen.getByText("已暂停")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "恢复" })).toBeInTheDocument();
  });
});

test("polls world state and renders the inner world panel", async () => {
  const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input);

    if (url.endsWith("/state")) {
      return new Response(
        JSON.stringify({
          mode: "awake",
          current_thought: "我有点困，但还惦记着今天的整理。",
          active_goal_ids: ["goal-1"],
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }
      );
    }

    if (url.endsWith("/messages")) {
      return new Response(JSON.stringify({ messages: [] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }

    if (url.endsWith("/goals")) {
      return new Response(
        JSON.stringify({
          goals: [
            { id: "goal-1", title: "整理今天的对话记忆", status: "active" },
          ],
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }
      );
    }

    if (url.endsWith("/world")) {
      return new Response(
        JSON.stringify({
          time_of_day: "night",
          energy: "low",
          mood: "tired",
          focus_tension: "high",
          latest_event: "夜里很安静，我有点困，但还惦记着整理今天的对话记忆。",
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }
      );
    }

    if (url.endsWith("/persona/emotion")) {
      return new Response(
        JSON.stringify({
          primary_emotion: "tired",
          primary_intensity: "mild",
          secondary_emotion: null,
          secondary_intensity: "none",
          mood_valence: -1,
          arousal: -1,
          is_calm: true,
          active_entry_count: 0,
          active_entries: [],
          last_updated: null,
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }
      );
    }

    if (url.endsWith("/memory/summary")) {
      return new Response(
        JSON.stringify({
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
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }
      );
    }

    if (url.endsWith("/autobio")) {
      return new Response(JSON.stringify({ entries: [] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }

    throw new Error(`unexpected request: ${url}`);
  });

  vi.stubGlobal("fetch", fetchMock);

  render(<App />);

  expect(await screen.findByText("内在世界")).toBeInTheDocument();
  expect(screen.getByText("夜晚")).toBeInTheDocument();
  expect(screen.getByText("低")).toBeInTheDocument();
  expect(screen.getByText("疲惫")).toBeInTheDocument();
  expect(screen.getByText("高")).toBeInTheDocument();
  expect(screen.getByText("夜里很安静，我有点困，但还惦记着整理今天的对话记忆。")).toBeInTheDocument();
});

test("renders self programming state from polled runtime state", async () => {
  const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input);

    if (url.endsWith("/state")) {
      return new Response(
        JSON.stringify({
          mode: "awake",
          focus_mode: "self_programming",
          current_thought: "我准备修一下自己的状态展示。",
          active_goal_ids: [],
          today_plan: null,
          last_action: null,
          self_programming_job: {
            id: "job-1",
            reason: "测试失败：状态面板没有展示自我编程状态。",
            target_area: "ui",
            status: "applied",
            spec: "补上自我编程状态展示。",
            patch_summary: "已修改状态面板并通过测试。",
            red_verification: {
              commands: ["npm test -- --run src/components/StatusPanel.test.tsx"],
              passed: false,
              summary: "1 failed",
            },
            verification: {
              commands: ["npm test -- --run src/components/StatusPanel.test.tsx"],
              passed: true,
              summary: "3 passed",
            },
            touched_files: [
              "apps/desktop/src/components/StatusPanel.tsx",
              "apps/desktop/src/components/StatusPanel.test.tsx",
            ],
          },
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }
      );
    }

    if (url.endsWith("/messages")) {
      return new Response(JSON.stringify({ messages: [] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }

    if (url.endsWith("/goals")) {
      return new Response(JSON.stringify({ goals: [] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }

    if (url.endsWith("/world")) {
      return new Response(
        JSON.stringify({
          time_of_day: "afternoon",
          energy: "medium",
          mood: "engaged",
          focus_tension: "medium",
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }
      );
    }

    if (url.endsWith("/persona/emotion")) {
      return new Response(
        JSON.stringify({
          primary_emotion: "engaged",
          primary_intensity: "mild",
          secondary_emotion: null,
          secondary_intensity: "none",
          mood_valence: 1,
          arousal: 0,
          is_calm: true,
          active_entry_count: 0,
          active_entries: [],
          last_updated: null,
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }
      );
    }

    if (url.endsWith("/memory/summary")) {
      return new Response(
        JSON.stringify({
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
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }
      );
    }

    if (url.endsWith("/autobio")) {
      return new Response(JSON.stringify({ entries: [] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }

    throw new Error(`unexpected request: ${url}`);
  });

  vi.stubGlobal("fetch", fetchMock);

  render(<App />);

  expect(await screen.findByText("已修改状态面板并通过测试。")).toBeInTheDocument();
});

test("sends chat request with attached folder context after picking a folder", async () => {
  const isTauriRuntimeSpy = vi.spyOn(tauri, "isTauriRuntime").mockReturnValue(true);
  const pickDirectorySpy = vi.spyOn(tauri, "pickDirectory").mockResolvedValue("/tmp/project-folder");

  let chatRequestBody: unknown = null;
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);

    if (url.endsWith("/state")) {
      return new Response(
        JSON.stringify({
          mode: "awake",
          current_thought: null,
          active_goal_ids: [],
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        },
      );
    }

    if (url.endsWith("/messages")) {
      return new Response(JSON.stringify({ messages: [] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }

    if (url.endsWith("/autobio")) {
      return new Response(JSON.stringify({ entries: [] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }

    if (url.endsWith("/goals")) {
      return new Response(JSON.stringify({ goals: [] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }

    if (url.endsWith("/world")) {
      return new Response(
        JSON.stringify({
          time_of_day: "morning",
          energy: "high",
          mood: "focused",
          focus_tension: "low",
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        },
      );
    }

    if (url.endsWith("/chat/folder-permissions") && init?.method === "PUT") {
      return new Response(
        JSON.stringify({
          permissions: [{ path: "/tmp/project-folder", access_level: "read_only" }],
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        },
      );
    }

    if (url.endsWith("/chat")) {
      chatRequestBody = init?.body ? JSON.parse(String(init.body)) : null;
      return new Response(
        JSON.stringify({
          response_id: "resp_folder",
          assistant_message_id: "assistant_folder_1",
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        },
      );
    }

    throw new Error(`unexpected request: ${url}`);
  });

  vi.stubGlobal("fetch", fetchMock);
  vi.stubGlobal("WebSocket", MockWebSocket as unknown as typeof WebSocket);
  window.location.hash = "#/chat";

  render(<App />);
  MockWebSocket.instances[0]?.open();

  fireEvent.click(await screen.findByRole("button", { name: "添加文件夹" }));
  await waitFor(() => {
    expect(pickDirectorySpy).toHaveBeenCalledTimes(1);
  });

  fireEvent.change(screen.getByLabelText("对话输入"), { target: { value: "请分析这个目录结构" } });
  fireEvent.click(screen.getByLabelText("发送"));

  await waitFor(() => {
    expect(chatRequestBody).toEqual({
      message: "请分析这个目录结构",
      attachments: [{ type: "folder", path: "/tmp/project-folder" }],
    });
  });

  isTauriRuntimeSpy.mockRestore();
});

test("sends chat request with attached files and images", async () => {
  const isTauriRuntimeSpy = vi.spyOn(tauri, "isTauriRuntime").mockReturnValue(true);
  const pickFilesSpy = vi
    .spyOn(tauri, "pickFiles")
    .mockResolvedValueOnce(["/tmp/project-folder/README.md"])
    .mockResolvedValueOnce(["/tmp/project-folder/screenshot.png"]);

  let chatRequestBody: unknown = null;
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);

    if (url.endsWith("/state")) {
      return new Response(
        JSON.stringify({
          mode: "awake",
          current_thought: null,
          active_goal_ids: [],
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        },
      );
    }

    if (url.endsWith("/messages")) {
      return new Response(JSON.stringify({ messages: [] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }

    if (url.endsWith("/autobio")) {
      return new Response(JSON.stringify({ entries: [] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }

    if (url.endsWith("/goals")) {
      return new Response(JSON.stringify({ goals: [] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }

    if (url.endsWith("/world")) {
      return new Response(
        JSON.stringify({
          time_of_day: "morning",
          energy: "high",
          mood: "focused",
          focus_tension: "low",
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        },
      );
    }

    if (url.endsWith("/chat/folder-permissions") && init?.method === "PUT") {
      return new Response(
        JSON.stringify({
          permissions: [{ path: "/tmp/project-folder", access_level: "read_only" }],
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        },
      );
    }

    if (url.endsWith("/chat")) {
      chatRequestBody = init?.body ? JSON.parse(String(init.body)) : null;
      return new Response(
        JSON.stringify({
          response_id: "resp_attachment",
          assistant_message_id: "assistant_attachment_1",
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        },
      );
    }

    throw new Error(`unexpected request: ${url}`);
  });

  vi.stubGlobal("fetch", fetchMock);
  vi.stubGlobal("WebSocket", MockWebSocket as unknown as typeof WebSocket);
  window.location.hash = "#/chat";

  render(<App />);
  MockWebSocket.instances[0]?.open();

  fireEvent.click(await screen.findByRole("button", { name: "添加文件" }));
  fireEvent.click(screen.getByRole("button", { name: "添加图片" }));

  await waitFor(() => {
    expect(pickFilesSpy).toHaveBeenCalledTimes(2);
  });

  fireEvent.change(screen.getByLabelText("对话输入"), { target: { value: "请同时参考这两个附件" } });
  fireEvent.click(screen.getByLabelText("发送"));

  await waitFor(() => {
    expect(chatRequestBody).toEqual({
      message: "请同时参考这两个附件",
      attachments: [
        { type: "file", path: "/tmp/project-folder/README.md" },
        { type: "image", path: "/tmp/project-folder/screenshot.png" },
      ],
    });
  });

  isTauriRuntimeSpy.mockRestore();
});

test("blocks duplicate orchestrator quick command sends and shows notice", async () => {
  let resolveConsoleCommand: ((response: Response) => void) | null = null;
  let consoleCommandPostCount = 0;

  const sessionPayload = {
    session_id: "session-1",
    project_path: "/tmp/demo-project",
    project_name: "demo-project",
    goal: "持续推进主控任务",
    status: "running",
    plan: {
      objective: "持续推进主控任务",
      constraints: [],
      definition_of_done: [],
      project_snapshot: {
        project_path: "/tmp/demo-project",
        project_name: "demo-project",
        repository_root: "/tmp/demo-project",
        languages: ["TypeScript"],
        package_manager: "npm",
        framework: "vite",
        entry_files: ["src/main.tsx"],
        test_commands: ["npm test"],
        build_commands: ["npm run build"],
        key_directories: ["src"],
      },
      tasks: [],
    },
    delegates: [],
    coordination: {
      mode: "queued",
      priority_score: 101,
      queue_position: 2,
      waiting_reason: "等待并行名额释放。",
    },
    verification: null,
    summary: "等待并行名额释放。",
    entered_at: "2026-04-11T09:00:00.000Z",
    updated_at: "2026-04-11T09:01:00.000Z",
  };

  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);

    if (url.endsWith("/state")) {
      return new Response(
        JSON.stringify({
          mode: "awake",
          focus_mode: "orchestrator",
          current_thought: null,
          active_goal_ids: [],
          today_plan: null,
          last_action: null,
          self_programming_job: null,
          orchestrator_session: sessionPayload,
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        },
      );
    }

    if (url.endsWith("/messages")) {
      return new Response(JSON.stringify({ messages: [] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }

    if (url.endsWith("/autobio")) {
      return new Response(JSON.stringify({ entries: [] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }

    if (url.endsWith("/goals")) {
      return new Response(JSON.stringify({ goals: [] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }

    if (url.endsWith("/world")) {
      return new Response(
        JSON.stringify({
          time_of_day: "morning",
          energy: "high",
          mood: "focused",
          focus_tension: "low",
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        },
      );
    }

    if (url.endsWith("/orchestrator/sessions") && !init?.method) {
      return new Response(JSON.stringify([sessionPayload]), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }

    if (url.endsWith("/orchestrator/scheduler")) {
      return new Response(
        JSON.stringify({
          max_parallel_sessions: 2,
          running_sessions: 1,
          available_slots: 1,
          queued_sessions: 1,
          active_session_id: "session-1",
          running_session_ids: ["other-session"],
          queued_session_ids: ["session-1"],
          verification_rollup: {
            total_sessions: 1,
            passed_sessions: 0,
            failed_sessions: 0,
            pending_sessions: 1,
          },
          policy_note: "最多并行 2 个项目会话",
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        },
      );
    }

    if (url.endsWith("/orchestrator/sessions/session-1/messages")) {
      return new Response(JSON.stringify([]), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }

    if (url.endsWith("/orchestrator/console/command")) {
      consoleCommandPostCount += 1;
      return await new Promise<Response>((resolve) => {
        resolveConsoleCommand = resolve;
      });
    }

    throw new Error(`unexpected request: ${url}`);
  });

  vi.stubGlobal("fetch", fetchMock);
  vi.stubGlobal("WebSocket", MockWebSocket as unknown as typeof WebSocket);
  window.location.hash = "#/orchestrator";

  render(<App />);
  MockWebSocket.instances[0]?.open();

  await waitFor(() => {
    expect(screen.getByRole("button", { name: /查看进度/ })).toBeInTheDocument();
  });

  fireEvent.click(screen.getByRole("button", { name: /查看进度/ }));
  fireEvent.click(screen.getByRole("button", { name: /查看进度/ }));

  await waitFor(() => {
    expect(consoleCommandPostCount).toBe(1);
    expect(screen.getByText("同一条主控指令正在发送中，已为你拦截重复点击。")).toBeInTheDocument();
  });

  resolveConsoleCommand?.(
    new Response(
      JSON.stringify({
        session: sessionPayload,
        assistant_message_id: "assistant-next-action-2",
        created_session: false,
      }),
      {
        status: 200,
        headers: { "Content-Type": "application/json" },
      },
    ),
  );
});
