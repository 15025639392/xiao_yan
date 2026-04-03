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

    if (url.endsWith("/autobio")) {
      return new Response(
        JSON.stringify({
          entries: [
            "我最近像是一路从第1步走到第3步，开始学着把这些变化连成自己的经历。",
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
  expect(
    screen.getByText("我最近像是一路从第1步走到第3步，开始学着把这些变化连成自己的经历。"),
  ).toBeInTheDocument();

  await act(async () => {
    await vi.advanceTimersByTimeAsync(5000);
    await vi.advanceTimersByTimeAsync(0);
  });

  expect(screen.getByText("Thought: 我刚刚又想到星星了。")).toBeInTheDocument();
  expect(screen.getByText("Xiao Yan: 我刚刚又想到你提到的星星了。")).toBeInTheDocument();
  expect(screen.getByText("整理昨晚关于夜空的聊天")).toBeInTheDocument();
});

test("updates a goal status from the app and refreshes the rendered goal", async () => {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);

    if (url.endsWith("/state")) {
      return new Response(
        JSON.stringify({
          mode: "awake",
          current_thought: "正在想用户刚刚说的话。",
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

  expect(await screen.findByText("active")).toBeInTheDocument();

  fireEvent.click(screen.getByText("Pause"));

  await waitFor(() => {
    expect(screen.getByText("paused")).toBeInTheDocument();
    expect(screen.getByText("Resume")).toBeInTheDocument();
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

  expect(await screen.findByText("Time: night")).toBeInTheDocument();
  expect(screen.getByText("Energy: low")).toBeInTheDocument();
  expect(screen.getByText("Mood: tired")).toBeInTheDocument();
  expect(screen.getByText("Focus: high")).toBeInTheDocument();
  expect(
    screen.getByText("Latest Event: 夜里很安静，我有点困，但还惦记着整理今天的对话记忆。")
  ).toBeInTheDocument();
});
