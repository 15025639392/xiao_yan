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
  expect(screen.getByRole("button", { name: "唤醒" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "休眠" })).toBeInTheDocument();
  expect(screen.getByText("指挥台")).toBeInTheDocument();
  expect(screen.getByText("对话控制台")).toBeInTheDocument();
  expect(screen.getByText("目标看板")).toBeInTheDocument();
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

  fireEvent.change(screen.getByLabelText("对话输入"), {
    target: { value: "hello xiao yan" },
  });
  fireEvent.click(screen.getByRole("button", { name: "发送" }));

  await waitFor(() => {
    expect(screen.getByText("hello xiao yan")).toBeInTheDocument();
    expect(screen.getByText("hello human")).toBeInTheDocument();
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
  expect(screen.getByText("当前状态")).toBeInTheDocument();
  expect(screen.getByText("持续理解用户最近在意的话题：星星")).toBeInTheDocument();
  expect(
    screen.getByText("我最近像是一路从第1步走到第3步，开始学着把这些变化连成自己的经历。"),
  ).toBeInTheDocument();

  await act(async () => {
    await vi.advanceTimersByTimeAsync(5000);
    await vi.advanceTimersByTimeAsync(0);
  });

  expect(screen.getByText("我刚刚又想到星星了。")).toBeInTheDocument();
  expect(screen.getByText("我刚刚又想到你提到的星星了。")).toBeInTheDocument();
  expect(screen.getByText("整理昨晚关于夜空的聊天")).toBeInTheDocument();
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
                      content: "把“持续理解用户最近在意的话题：星星”的轮廓理一下",
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
    expect(screen.getAllByText("常规自主")).toHaveLength(2);
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

test("renders self improvement state from polled runtime state", async () => {
  const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input);

    if (url.endsWith("/state")) {
      return new Response(
        JSON.stringify({
          mode: "awake",
          focus_mode: "self_improvement",
          current_thought: "我准备修一下自己的状态展示。",
          active_goal_ids: [],
          today_plan: null,
          last_action: null,
          self_improvement_job: {
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

  expect(await screen.findAllByText("自我修复")).toHaveLength(2);
  expect(screen.getByText("她刚刚为什么改自己")).toBeInTheDocument();
  expect(screen.getByText("已修改状态面板并通过测试。")).toBeInTheDocument();
  expect(screen.getByText("1 failed")).toBeInTheDocument();
  expect(screen.getByText("通过")).toBeInTheDocument();
  expect(screen.getByText("apps/desktop/src/components/StatusPanel.tsx, apps/desktop/src/components/StatusPanel.test.tsx")).toBeInTheDocument();
});
