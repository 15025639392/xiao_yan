import { act, fireEvent, render as rtlRender, screen, waitFor, within } from "@testing-library/react";
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
  window.localStorage.removeItem(IMPORTED_PROJECTS_STORAGE_KEY);
  window.location.hash = "";
  MockWebSocket.instances = [];
});

async function renderApp() {
  let view: ReturnType<typeof rtlRender> | null = null;

  await act(async () => {
    view = rtlRender(<App />);
  });

  return view!;
}

async function openRealtimeSocket() {
  const socket = MockWebSocket.instances.at(-1);
  if (!socket) {
    throw new Error("expected App to create a websocket connection");
  }

  await act(async () => {
    socket.open();
    await Promise.resolve();
  });

  return socket;
}

function jsonResponse(body: unknown, init?: ResponseInit) {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
    ...init,
  });
}

type FetchHandler = (url: string, init?: RequestInit) => Response | Promise<Response> | null | undefined;

function createAppShellFetchMock(handlers: FetchHandler[] = []) {
  return vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);

    for (const handler of handlers) {
      const response = await handler(url, init);
      if (response) {
        return response;
      }
    }

    if (url.endsWith("/world")) {
      return jsonResponse({
        time_of_day: "night",
        energy: "low",
        mood: "tired",
        focus_tension: "low",
      });
    }
    if (url.endsWith("/goals")) {
      return jsonResponse({ goals: [] });
    }
    if (url.endsWith("/goals/admission/stats")) {
      return jsonResponse({
        mode: "off",
        today: { admit: 0, defer: 0, drop: 0, wip_blocked: 0 },
        admitted_stability_24h: { stable: 0, re_deferred: 0, dropped: 0 },
        admitted_stability_24h_rate: null,
        deferred_queue_size: 0,
        wip_limit: 3,
        thresholds: {
          user_topic: { min_score: 0.6, defer_score: 0.4 },
          chain_next: { min_score: 0.6, defer_score: 0.4 },
        },
      });
    }
    if (url.endsWith("/goals/admission/candidates")) {
      return jsonResponse({ deferred: [], recent: [] });
    }
    if (url.includes("/config/goal-admission/history")) {
      return jsonResponse({ items: [] });
    }
    if (url.endsWith("/messages")) {
      return jsonResponse({ messages: [] });
    }
    if (url.endsWith("/persona/emotion")) {
      return jsonResponse({
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
      });
    }
    if (url.endsWith("/memory/summary")) {
      return jsonResponse({
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
    }
    if (url.includes("/memory/timeline")) {
      return jsonResponse({ entries: [] });
    }

    return jsonResponse({
      mode: "sleeping",
      current_thought: null,
      active_goal_ids: [],
    });
  });
}

test("renders wake and sleep controls", async () => {
  vi.stubGlobal("fetch", createAppShellFetchMock());

  const { container } = await renderApp();
  const mainNav = screen.getByRole("navigation", { name: "主导航" });
  expect(screen.getByRole("button", { name: "唤醒" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "休眠" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "对话" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "总览" })).toBeInTheDocument();
  expect(within(mainNav).queryByRole("button", { name: "记忆" })).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "记忆库" })).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "能力中枢" })).not.toBeInTheDocument();
  expect(screen.getByText("小晏")).toBeInTheDocument();
  expect(screen.getByText("目标看板")).toBeInTheDocument();
  expect(container.querySelector(".app-layout")).toBeTruthy();
  expect(container.querySelector(".app-sidebar")).toBeTruthy();
  expect(container.querySelector(".overview-stage")).toBeTruthy();
  expect(container.querySelector(".inspector-grid")).toBeTruthy();
});

test("keeps memory reachable as an optional entry instead of a primary nav item", async () => {
  vi.stubGlobal("fetch", createAppShellFetchMock());

  await renderApp();

  fireEvent.click(screen.getByRole("button", { name: "记忆库" }));

  await waitFor(() => {
    expect(screen.getByRole("heading", { name: "记忆库" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "全部记忆" })).toBeInTheDocument();
  });
});

test("redirects legacy history route to overview and keeps memory as secondary entry", async () => {
  vi.stubGlobal("fetch", createAppShellFetchMock());
  window.location.hash = "#/history";

  await renderApp();

  await waitFor(() => {
    expect(window.location.hash).toBe("#/");
  });
  expect(screen.getByRole("button", { name: "记忆库" })).toBeInTheDocument();
});

test("redirects legacy orchestrator route to overview", async () => {
  vi.stubGlobal("fetch", createAppShellFetchMock());
  window.location.hash = "#/orchestrator";

  await renderApp();

  await waitFor(() => {
    expect(window.location.hash).toBe("#/");
  });
  expect(screen.getByRole("button", { name: "总览" })).toBeInTheDocument();
});

test("renders capability hub when route is capabilities", async () => {
  const fetchMock = createAppShellFetchMock([
    (url) => {
      if (url.endsWith("/capabilities/contract")) {
        return jsonResponse({
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
        });
      }
      if (url.endsWith("/capabilities/queue/status")) {
        return jsonResponse({
          pending: 1,
          pending_approval: 0,
          in_progress: 1,
          completed: 12,
          dead_letter: 0,
        });
      }
      if (url.includes("/capabilities/jobs")) {
        return jsonResponse({ items: [], next_cursor: null });
      }
      if (url.includes("/capabilities/approvals/pending")) {
        return jsonResponse({ items: [] });
      }
      if (url.includes("/capabilities/approvals/history")) {
        return jsonResponse({ items: [] });
      }
      if (url.endsWith("/state")) {
        return jsonResponse({
          mode: "awake",
          current_thought: null,
          active_goal_ids: [],
        });
      }
      return null;
    },
  ]);

  vi.stubGlobal("fetch", fetchMock);
  window.location.hash = "#/capabilities";

  await renderApp();

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
      expect(JSON.parse(String(init?.body ?? "{}"))).toMatchObject({ message: "hello xiao yan" });
      return await new Promise<Response>((resolve) => {
        resolveChatRequest = resolve;
      });
    }

    throw new Error(`unexpected request: ${url}`);
  });

  vi.stubGlobal("fetch", fetchMock);
  vi.stubGlobal("WebSocket", MockWebSocket as unknown as typeof WebSocket);
  window.location.hash = "#/chat";

  await renderApp();
  const socket = await openRealtimeSocket();
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

  await act(async () => {
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
    await Promise.resolve();
  });

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
      expect(JSON.parse(String(init?.body ?? "{}"))).toMatchObject({ message: "请重发这条消息" });

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

  await renderApp();
  const socket = await openRealtimeSocket();

  fireEvent.change(screen.getByLabelText("对话输入"), {
    target: { value: "请重发这条消息" },
  });
  fireEvent.click(screen.getByLabelText("发送"));

  await waitFor(() => {
    expect(screen.getByRole("button", { name: "重新发送" })).toBeInTheDocument();
    expect(screen.getByText(/这句话还没顺利送到小晏那里/)).toBeInTheDocument();
    expect(screen.getAllByText(/upstream timeout/).length).toBeGreaterThanOrEqual(1);
  });

  fireEvent.click(screen.getByRole("button", { name: "重新发送" }));

  await waitFor(() => {
    expect(chatCallCount).toBe(2);
  });

  await waitFor(() => {
    expect(screen.queryByRole("button", { name: "重新发送" })).not.toBeInTheDocument();
  });

  expect(screen.getByDisplayValue("请重发这条消息")).toBeInTheDocument();
  expect(screen.getAllByText("请重发这条消息").length).toBeGreaterThanOrEqual(1);
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
      expect(JSON.parse(String(init?.body ?? "{}"))).toMatchObject({
        message: "用 browser 工具检查页面",
        mcp_servers: ["browser"],
      });
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

  await renderApp();
  const socket = await openRealtimeSocket();

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

test("sends reasoning payload when bootstrap config enables continuous reasoning", async () => {
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
          chat_continuous_reasoning_enabled: true,
          chat_mcp_enabled: false,
          chat_mcp_servers: [],
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
      expect(JSON.parse(String(init?.body ?? "{}"))).toMatchObject({
        message: "继续说",
        reasoning: { enabled: true },
      });
      return new Response(
        JSON.stringify({
          response_id: "resp_reasoning_bootstrap_1",
          assistant_message_id: "assistant_reasoning_bootstrap_1",
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

  await renderApp();
  const socket = await openRealtimeSocket();

  fireEvent.change(screen.getByLabelText("对话输入"), {
    target: { value: "继续说" },
  });
  fireEvent.click(screen.getByLabelText("发送"));

  await waitFor(() => {
    expect(chatRequested).toBe(true);
  });
});

test("reuses latest reasoning session id for the next normal chat turn", async () => {
  let chatCallCount = 0;
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    const method = init?.method ?? "GET";

    if (url.endsWith("/state")) {
      return jsonResponse({
        mode: "awake",
        current_thought: null,
        active_goal_ids: [],
      });
    }

    if (url.endsWith("/messages")) {
      return jsonResponse({ messages: [] });
    }

    if (url.endsWith("/goals")) {
      return jsonResponse({ goals: [] });
    }

    if (url.endsWith("/world")) {
      return jsonResponse({
        time_of_day: "morning",
        energy: "high",
        mood: "engaged",
        focus_tension: "low",
      });
    }

    if (url.endsWith("/config") && method === "GET") {
      return jsonResponse({
        chat_context_limit: 6,
        chat_provider: "openai",
        chat_model: "gpt-5.4",
        chat_read_timeout_seconds: 180,
        chat_continuous_reasoning_enabled: true,
        chat_mcp_enabled: false,
        chat_mcp_servers: [],
      });
    }

    if (url.endsWith("/chat")) {
      chatCallCount += 1;
      expect(init?.method).toBe("POST");
      const body = JSON.parse(String(init?.body ?? "{}"));
      if (chatCallCount === 1) {
        expect(body).toMatchObject({
          message: "先继续说",
          reasoning: { enabled: true },
        });
        expect(body.reasoning.session_id).toBeUndefined();
        return jsonResponse({
          response_id: "resp_reasoning_turn_1",
          assistant_message_id: "assistant_reasoning_turn_1",
        });
      }

      expect(body).toEqual({
        message: "再往下接着聊",
        reasoning: {
          enabled: true,
          session_id: "reasoning_turn_shared_1",
        },
      });
      return jsonResponse({
        response_id: "resp_reasoning_turn_2",
        assistant_message_id: "assistant_reasoning_turn_2",
      });
    }

    throw new Error(`unexpected request: ${url}`);
  });

  vi.stubGlobal("fetch", fetchMock);
  vi.stubGlobal("WebSocket", MockWebSocket as unknown as typeof WebSocket);
  window.location.hash = "#/chat";

  await renderApp();
  const socket = await openRealtimeSocket();

  fireEvent.change(screen.getByLabelText("对话输入"), {
    target: { value: "先继续说" },
  });
  fireEvent.click(screen.getByLabelText("发送"));

  await waitFor(() => {
    expect(chatCallCount).toBe(1);
  });

  await act(async () => {
    socket.emit({
      type: "chat_started",
      payload: {
        assistant_message_id: "assistant_reasoning_turn_1",
        response_id: "resp_reasoning_turn_1",
        reasoning_session_id: "reasoning_turn_shared_1",
        reasoning_state: {
          session_id: "reasoning_turn_shared_1",
          phase: "exploring",
          step_index: 1,
          summary: "先接住当前线索",
          updated_at: "2026-04-18T10:00:00Z",
        },
      },
    });
  });

  await act(async () => {
    socket.emit({
      type: "chat_completed",
      payload: {
        assistant_message_id: "assistant_reasoning_turn_1",
        response_id: "resp_reasoning_turn_1",
        content: "我先接住这条线。",
        reasoning_session_id: "reasoning_turn_shared_1",
        reasoning_state: {
          session_id: "reasoning_turn_shared_1",
          phase: "completed",
          step_index: 1,
          summary: "先接住当前线索",
          updated_at: "2026-04-18T10:00:05Z",
        },
      },
    });
  });

  await waitFor(() => {
    expect(screen.getByText("我先接住这条线。")).toBeInTheDocument();
  });

  fireEvent.change(screen.getByLabelText("对话输入"), {
    target: { value: "再往下接着聊" },
  });
  fireEvent.click(screen.getByLabelText("发送"));

  await waitFor(() => {
    expect(chatCallCount).toBe(2);
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

  await renderApp();
  const socket = await openRealtimeSocket();

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
      expect(JSON.parse(String(init?.body ?? "{}"))).toMatchObject({ message: "你好" });
      return await new Promise<Response>((resolve) => {
        resolveChatRequest = resolve;
      });
    }

    throw new Error(`unexpected request: ${url}`);
  });

  vi.stubGlobal("fetch", fetchMock);
  vi.stubGlobal("WebSocket", MockWebSocket as unknown as typeof WebSocket);
  window.location.hash = "#/chat";

  await renderApp();
  const socket = await openRealtimeSocket();

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

    throw new Error(`unexpected request: ${url}`);
  });

  vi.stubGlobal("fetch", fetchMock);
  vi.stubGlobal("WebSocket", MockWebSocket as unknown as typeof WebSocket);
  window.location.hash = "#/chat";

  await renderApp();
  const socket = await openRealtimeSocket();

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

  await renderApp();
  const socket = await openRealtimeSocket();

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

  await act(async () => {
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
    await Promise.resolve();
  });
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

  await renderApp();
  const socket = await openRealtimeSocket();

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

  await act(async () => {
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
    await Promise.resolve();
  });
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

  await renderApp();

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
      expect(JSON.parse(String(init?.body ?? "{}"))).toMatchObject({ message: "hello" });
      return await new Promise<Response>((resolve) => {
        resolveChatRequest = resolve;
      });
    }

    throw new Error(`unexpected request: ${url}`);
  });

  vi.stubGlobal("fetch", fetchMock);
  vi.stubGlobal("WebSocket", MockWebSocket as unknown as typeof WebSocket);
  window.location.hash = "#/chat";

  await renderApp();
  const socket = await openRealtimeSocket();

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

  await act(async () => {
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
    await Promise.resolve();
  });
});

test("continues generation in the same assistant bubble after failure", async () => {
  let resolveChatRequest: ((response: Response) => void) | null = null;
  let resolveResumeRequest: ((response: Response) => void) | null = null;
  const reasoningSessionId = "reasoning_resume_1";
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    const method = init?.method ?? "GET";

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

    if (url.endsWith("/config") && method === "GET") {
      return new Response(
        JSON.stringify({
          chat_context_limit: 6,
          chat_provider: "openai",
          chat_model: "gpt-5.4",
          chat_read_timeout_seconds: 180,
          chat_continuous_reasoning_enabled: false,
          chat_mcp_enabled: false,
          chat_mcp_servers: [],
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

    if (url.endsWith("/config") && method === "PUT") {
      expect(init?.body).toBe(JSON.stringify({ chat_continuous_reasoning_enabled: true }));
      return new Response(
        JSON.stringify({
          chat_context_limit: 6,
          chat_provider: "openai",
          chat_model: "gpt-5.4",
          chat_read_timeout_seconds: 180,
          chat_continuous_reasoning_enabled: true,
          chat_mcp_enabled: false,
          chat_mcp_servers: [],
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        },
      );
    }

    if (url.endsWith("/chat/resume")) {
      expect(init?.method).toBe("POST");
      expect(JSON.parse(String(init?.body ?? "{}"))).toMatchObject({
        message: "继续说",
        assistant_message_id: "assistant_resume_1",
        partial_content: "前半句，",
        reasoning_session_id: reasoningSessionId,
      });
      return await new Promise<Response>((resolve) => {
        resolveResumeRequest = resolve;
      });
    }

    if (url.endsWith("/chat")) {
      expect(init?.method).toBe("POST");
      expect(init?.body).toBe(
        JSON.stringify({
          message: "继续说",
          reasoning: { enabled: true },
        }),
      );
      return await new Promise<Response>((resolve) => {
        resolveChatRequest = resolve;
      });
    }

    throw new Error(`unexpected request: ${url}`);
  });

  vi.stubGlobal("fetch", fetchMock);
  vi.stubGlobal("WebSocket", MockWebSocket as unknown as typeof WebSocket);
  window.location.hash = "#/chat";

  await renderApp();
  const socket = await openRealtimeSocket();

  fireEvent.click(screen.getByRole("button", { name: "⚙️ 配置" }));
  fireEvent.click(await screen.findByLabelText("启用持续推理"));
  fireEvent.click(screen.getByLabelText("关闭"));

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
        reasoning_session_id: reasoningSessionId,
        reasoning_state: {
          session_id: reasoningSessionId,
          phase: "planning",
          step_index: 1,
          summary: "规划续写步骤",
          updated_at: "2026-04-16T10:00:00Z",
        },
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

  await act(async () => {
    resolveChatRequest?.(
      new Response(JSON.stringify({ detail: "Bad Gateway" }), {
        status: 502,
        headers: { "Content-Type": "application/json" },
      }),
    );
    await Promise.resolve();
  });

  await waitFor(() => {
    expect(screen.getByText("前半句，")).toBeInTheDocument();
    expect(screen.getByText("小晏刚才停下来了：request failed: 502")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "接着说完" })).toBeInTheDocument();
  });

  fireEvent.click(screen.getByRole("button", { name: "接着说完" }));

  await act(async () => {
    socket.emit({
      type: "chat_started",
      payload: {
        assistant_message_id: "assistant_resume_1",
        response_id: "resp_resume_1",
        reasoning_session_id: reasoningSessionId,
        reasoning_state: {
          session_id: reasoningSessionId,
          phase: "exploring",
          step_index: 2,
          summary: "继续补全后半句",
          updated_at: "2026-04-16T10:00:20Z",
        },
      },
    });
  });

  await act(async () => {
    socket.emit({
      type: "chat_delta",
      payload: {
        assistant_message_id: "assistant_resume_1",
        delta: "后半句。",
        reasoning_session_id: reasoningSessionId,
        reasoning_state: {
          session_id: reasoningSessionId,
          phase: "finalizing",
          step_index: 3,
          summary: "整理最终回答",
          updated_at: "2026-04-16T10:00:30Z",
        },
      },
    });
  });

  await waitFor(() => {
    expect(screen.getByText("前半句，后半句。▍")).toBeInTheDocument();
  });

  await act(async () => {
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
    await Promise.resolve();
  });

  await act(async () => {
    socket.emit({
      type: "chat_completed",
      payload: {
        assistant_message_id: "assistant_resume_1",
        response_id: "resp_resume_1",
        content: "前半句，后半句。",
        reasoning_session_id: reasoningSessionId,
        reasoning_state: {
          session_id: reasoningSessionId,
          phase: "completed",
          step_index: 4,
          summary: "续写完成",
          updated_at: "2026-04-16T10:00:40Z",
        },
      },
    });
  });

  await waitFor(() => {
    expect(screen.getByText("前半句，后半句。")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "接着说完" })).not.toBeInTheDocument();
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
      expect(JSON.parse(String(init?.body ?? "{}"))).toMatchObject({ message: "你好" });
      return await new Promise<Response>((resolve) => {
        resolveChatRequest = resolve;
      });
    }

    throw new Error(`unexpected request: ${url}`);
  });

  vi.stubGlobal("fetch", fetchMock);
  vi.stubGlobal("WebSocket", MockWebSocket as unknown as typeof WebSocket);
  window.location.hash = "#/chat";

  await renderApp();
  const socket = await openRealtimeSocket();

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

  await act(async () => {
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
    await Promise.resolve();
  });

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

test("does not duplicate a completed assistant reply when runtime history replays it with persisted ids", async () => {
  let resolveChatRequest: ((response: Response) => void) | null = null;
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);

    if (url.endsWith("/state")) {
      return jsonResponse({
        mode: "awake",
        focus_mode: "autonomy",
        current_thought: null,
        active_goal_ids: [],
        today_plan: null,
        last_action: null,
      });
    }

    if (url.endsWith("/messages")) {
      return jsonResponse({ messages: [] });
    }

    if (url.endsWith("/goals")) {
      return jsonResponse({ goals: [] });
    }

    if (url.endsWith("/world")) {
      return jsonResponse({
        time_of_day: "morning",
        energy: "high",
        mood: "engaged",
        focus_tension: "low",
      });
    }

    if (url.endsWith("/chat")) {
      expect(init?.method).toBe("POST");
      expect(JSON.parse(String(init?.body ?? "{}"))).toMatchObject({ message: "你好" });
      return await new Promise<Response>((resolve) => {
        resolveChatRequest = resolve;
      });
    }

    throw new Error(`unexpected request: ${url}`);
  });

  vi.stubGlobal("fetch", fetchMock);
  vi.stubGlobal("WebSocket", MockWebSocket as unknown as typeof WebSocket);
  window.location.hash = "#/chat";

  await renderApp();
  const socket = await openRealtimeSocket();

  fireEvent.change(screen.getByLabelText("对话输入"), {
    target: { value: "你好" },
  });
  fireEvent.click(screen.getByLabelText("发送"));

  await act(async () => {
    socket.emit({
      type: "chat_started",
      payload: {
        assistant_message_id: "assistant_local_done_1",
        response_id: "resp_local_done_1",
        session_id: "assistant_local_done_1",
        request_key: "request_local_done_1",
        sequence: 1,
      },
    });
  });

  await act(async () => {
    socket.emit({
      type: "chat_delta",
      payload: {
        assistant_message_id: "assistant_local_done_1",
        delta: "你好呀",
        session_id: "assistant_local_done_1",
        request_key: "request_local_done_1",
        sequence: 2,
      },
    });
  });

  await waitFor(() => {
    expect(screen.getByText("你好呀▍")).toBeInTheDocument();
  });

  await act(async () => {
    resolveChatRequest?.(
      jsonResponse({
        response_id: "resp_local_done_1",
        assistant_message_id: "assistant_local_done_1",
      }),
    );
    await Promise.resolve();
  });

  await act(async () => {
    socket.emit({
      type: "chat_completed",
      payload: {
        assistant_message_id: "assistant_local_done_1",
        response_id: "resp_local_done_1",
        content: "你好呀",
        session_id: "assistant_local_done_1",
        request_key: "request_local_done_1",
        sequence: 3,
      },
    });
  });

  await waitFor(() => {
    expect(screen.getByText("你好呀")).toBeInTheDocument();
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
        },
        messages: [
          {
            id: "mem-user-done-1",
            role: "user",
            content: "你好",
            request_key: "request_local_done_1",
          },
          {
            id: "mem-assistant-done-1",
            role: "assistant",
            content: "你好呀",
            request_key: "request_local_done_1",
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
    expect(screen.getByText("你好呀")).toBeInTheDocument();
  });

  expect(screen.queryAllByText("你好呀")).toHaveLength(1);
  expect(screen.queryAllByText("你好")).toHaveLength(1);
});

test("clears transient failed user state when runtime history brings back the retried turn", async () => {
  let chatCallCount = 0;
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);

    if (url.endsWith("/state")) {
      return jsonResponse({
        mode: "awake",
        focus_mode: "autonomy",
        current_thought: null,
        active_goal_ids: [],
        today_plan: null,
        last_action: null,
      });
    }

    if (url.endsWith("/messages")) {
      return jsonResponse({ messages: [] });
    }

    if (url.endsWith("/goals")) {
      return jsonResponse({ goals: [] });
    }

    if (url.endsWith("/world")) {
      return jsonResponse({
        time_of_day: "morning",
        energy: "high",
        mood: "engaged",
        focus_tension: "low",
      });
    }

    if (url.endsWith("/chat")) {
      chatCallCount += 1;
      expect(init?.method).toBe("POST");
      expect(JSON.parse(String(init?.body ?? "{}"))).toMatchObject({ message: "请帮我继续" });

      if (chatCallCount === 1) {
        return new Response(JSON.stringify({ detail: "network timeout" }), {
          status: 502,
          headers: { "Content-Type": "application/json" },
        });
      }

      return jsonResponse({
        response_id: "resp_retry_runtime_1",
        assistant_message_id: "assistant_retry_runtime_1",
      });
    }

    throw new Error(`unexpected request: ${url}`);
  });

  vi.stubGlobal("fetch", fetchMock);
  vi.stubGlobal("WebSocket", MockWebSocket as unknown as typeof WebSocket);
  window.location.hash = "#/chat";

  await renderApp();
  const socket = await openRealtimeSocket();

  fireEvent.change(screen.getByLabelText("对话输入"), {
    target: { value: "请帮我继续" },
  });
  fireEvent.click(screen.getByLabelText("发送"));

  await waitFor(() => {
    expect(screen.getByRole("button", { name: "重新发送" })).toBeInTheDocument();
    expect(screen.getAllByText(/network timeout/).length).toBeGreaterThan(0);
  });

  fireEvent.click(screen.getByRole("button", { name: "重新发送" }));

  await waitFor(() => {
    expect(chatCallCount).toBe(2);
    expect(screen.queryByRole("button", { name: "重新发送" })).not.toBeInTheDocument();
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
        },
        messages: [
          {
            id: "mem-user-retried-1",
            role: "user",
            content: "请帮我继续",
          },
          {
            id: "mem-assistant-retried-1",
            role: "assistant",
            content: "我接着说下去。",
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
    expect(screen.getByText("我接着说下去。")).toBeInTheDocument();
  });

  expect(screen.queryByRole("button", { name: "重新发送" })).not.toBeInTheDocument();
  expect(screen.queryByText(/这句话还没顺利送到小晏那里/)).toBeNull();
  expect(screen.getAllByText("请帮我继续").length).toBeGreaterThanOrEqual(1);
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

  await renderApp();

  // 等待初始加载
  await waitFor(() => {
    expect(screen.getByText("自由对话")).toBeInTheDocument();
  });

  const socket = await openRealtimeSocket();

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

  await renderApp();

  await waitFor(() => {
    expect(screen.getByText("小晏")).toBeInTheDocument();
  });

  const socket = await openRealtimeSocket();

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
    expect(screen.getByText("和阿晏说说现在的事")).toBeInTheDocument();
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

  await renderApp();

  expect(await screen.findByText("持续理解用户最近在意的话题：星星")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "暂停" })).toBeInTheDocument();

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

    throw new Error(`unexpected request: ${url}`);
  });

  vi.stubGlobal("fetch", fetchMock);

  await renderApp();

  expect(await screen.findByText("内在世界")).toBeInTheDocument();
  expect(screen.getByText("时间感")).toBeInTheDocument();
  expect(screen.getByText("能量")).toBeInTheDocument();
  expect(screen.getByText("情绪")).toBeInTheDocument();
  expect(screen.getByText("专注张力")).toBeInTheDocument();
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

  await renderApp();
  await openRealtimeSocket();

  fireEvent.click(await screen.findByRole("button", { name: "添加文件夹" }));
  await waitFor(() => {
    expect(pickDirectorySpy).toHaveBeenCalledTimes(1);
  });

  fireEvent.change(screen.getByLabelText("对话输入"), { target: { value: "请分析这个目录结构" } });
  fireEvent.click(screen.getByLabelText("发送"));

  await waitFor(() => {
    expect(chatRequestBody).toMatchObject({
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

  await renderApp();
  await openRealtimeSocket();

  fireEvent.click(await screen.findByRole("button", { name: "添加文件" }));
  fireEvent.click(screen.getByRole("button", { name: "添加图片" }));

  await waitFor(() => {
    expect(pickFilesSpy).toHaveBeenCalledTimes(2);
  });

  fireEvent.change(screen.getByLabelText("对话输入"), { target: { value: "请同时参考这两个附件" } });
  fireEvent.click(screen.getByLabelText("发送"));

  await waitFor(() => {
    expect(chatRequestBody).toMatchObject({
      message: "请同时参考这两个附件",
      attachments: [
        { type: "file", path: "/tmp/project-folder/README.md" },
        { type: "image", path: "/tmp/project-folder/screenshot.png" },
      ],
    });
  });

  isTauriRuntimeSpy.mockRestore();
});
