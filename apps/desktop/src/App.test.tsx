import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, vi } from "vitest";

import App from "./App";

afterEach(() => {
  vi.restoreAllMocks();
  vi.useRealTimers();
});

test("renders wake and sleep controls", () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
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

  render(<App />);
  expect(screen.getByText("Wake")).toBeInTheDocument();
  expect(screen.getByText("Sleep")).toBeInTheDocument();
});

test("sends a chat message and renders the assistant reply", async () => {
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

    if (url.endsWith("/chat")) {
      expect(init?.method).toBe("POST");
      expect(init?.body).toBe(JSON.stringify({ message: "hello xiao yan" }));
      return new Response(
        JSON.stringify({
          response_id: "resp_123",
          output_text: "hello human",
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

  fireEvent.change(screen.getByLabelText("Chat Input"), {
    target: { value: "hello xiao yan" },
  });
  fireEvent.click(screen.getByText("Send"));

  await waitFor(() => {
    expect(screen.getByText("You: hello xiao yan")).toBeInTheDocument();
    expect(screen.getByText("Xiao Yan: hello human")).toBeInTheDocument();
  });
});

test("polls state and messages so proactive replies appear in the chat panel", async () => {
  vi.useFakeTimers();

  let stateCallCount = 0;
  let messagesCallCount = 0;
  let goalsCallCount = 0;

  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);

    if (url.endsWith("/state")) {
      stateCallCount += 1;
      const body =
        stateCallCount === 1
          ? {
              mode: "awake",
              current_thought: "我醒了。",
              active_goal_ids: [],
            }
          : {
              mode: "awake",
              current_thought: "我刚刚又想到星星了。",
              active_goal_ids: [],
            };
      return new Response(JSON.stringify(body), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }

    if (url.endsWith("/messages")) {
      messagesCallCount += 1;
      const body =
        messagesCallCount === 1
          ? { messages: [] }
          : {
              messages: [
                { role: "assistant", content: "我刚刚又想到你提到的星星了。" },
              ],
            };
      return new Response(JSON.stringify(body), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }

    if (url.endsWith("/goals")) {
      goalsCallCount += 1;
      const body =
        goalsCallCount === 1
          ? {
              goals: [
                { id: "goal-1", title: "持续理解用户最近在意的话题：星星", status: "active" },
              ],
            }
          : {
              goals: [
                { id: "goal-1", title: "持续理解用户最近在意的话题：星星", status: "active" },
                { id: "goal-2", title: "整理昨晚关于夜空的聊天", status: "active" },
              ],
            };
      return new Response(JSON.stringify(body), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }

    if (url.endsWith("/chat")) {
      return new Response(
        JSON.stringify({
          response_id: "resp_123",
          output_text: "hello human",
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }
      );
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
  });

  vi.stubGlobal("fetch", fetchMock);

  render(<App />);

  await act(async () => {
    await vi.advanceTimersByTimeAsync(0);
  });
  expect(screen.getByText("Mode: awake")).toBeInTheDocument();
  expect(screen.getByText("持续理解用户最近在意的话题：星星")).toBeInTheDocument();

  await act(async () => {
    await vi.advanceTimersByTimeAsync(5000);
    await vi.advanceTimersByTimeAsync(0);
  });

  expect(screen.getByText("Thought: 我刚刚又想到星星了。")).toBeInTheDocument();
  expect(screen.getByText("Xiao Yan: 我刚刚又想到你提到的星星了。")).toBeInTheDocument();
  expect(screen.getByText("整理昨晚关于夜空的聊天")).toBeInTheDocument();
});
