import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, vi } from "vitest";

import App from "./App";
import { resetAppRealtimeForTests } from "./lib/realtime";

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
