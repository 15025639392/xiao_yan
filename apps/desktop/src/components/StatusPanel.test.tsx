import { act, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, vi } from "vitest";

const { fetchEmotionState, fetchMemorySummary } = vi.hoisted(() => ({
  fetchEmotionState: vi.fn(),
  fetchMemorySummary: vi.fn(),
}));

const { subscribeAppRealtime } = vi.hoisted(() => ({
  subscribeAppRealtime: vi.fn(),
}));

vi.mock("../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../lib/api")>("../lib/api");
  return {
    ...actual,
    fetchEmotionState,
    fetchMemorySummary,
  };
});

vi.mock("../lib/realtime", () => ({
  subscribeAppRealtime,
}));

import { StatusPanel } from "./StatusPanel";

beforeEach(() => {
  fetchEmotionState.mockReset();
  fetchMemorySummary.mockReset();
  subscribeAppRealtime.mockReset();

  fetchEmotionState.mockReturnValue(new Promise(() => {}));
  fetchMemorySummary.mockReturnValue(new Promise(() => {}));
  subscribeAppRealtime.mockReturnValue(() => {});
});

test("renders her plan for today when a morning plan exists", () => {
  render(
    <StatusPanel
      error=""
      focusGoalTitle="整理今天的对话记忆"
      focusContext={{
        goal_title: "整理今天的对话记忆",
        source_kind: "user_topic_goal",
        source_label: "刚接住你这轮话题的事",
        reason_kind: "today_plan_pending",
        reason_label: "今天这条还剩 2 步没做完",
        prompt_summary: "当前焦点来自刚接住你这轮话题的事，之所以还在推进，是因为今天这条还剩 2 步没做完。",
      }}
      state={{
        mode: "awake",
        focus_mode: "morning_plan",
        current_thought: "今天先把轮廓理一下。",
        active_goal_ids: ["goal-1"],
        focus_effort: {
          goal_id: "goal-1",
          goal_title: "整理今天的对话记忆",
          why_now: "今天计划已经排到这一步，需要先把当前小步走完。",
          action_kind: "plan_step",
          did_what: "推进了计划步骤：把「整理今天的对话记忆」的轮廓理一下",
          effect: "今天计划已完成 1/2 步。",
          next_hint: "接下来会继续走下一步。",
          created_at: "2026-04-18T06:30:00.000Z",
        },
        last_action: null,
        today_plan: {
          goal_id: "goal-1",
          goal_title: "整理今天的对话记忆",
          steps: [
            { content: "把「整理今天的对话记忆」的轮廓理一下", status: "pending" },
            { content: "开始动手推进", status: "pending" },
          ],
        },
      }}
    />
  );

  expect(screen.getAllByText("今日计划").length).toBeGreaterThanOrEqual(1);
  expect(screen.getByText("当前日程与运行状态")).toBeInTheDocument();
  expect(screen.getByText("当前焦点")).toBeInTheDocument();
  expect(screen.getAllByText("整理今天的对话记忆").length).toBeGreaterThanOrEqual(2);
  expect(screen.getByText("用户触发")).toBeInTheDocument();
  expect(screen.getByText("会先盯着这件事，因为这是刚接住你这轮话题的事。")).toBeInTheDocument();
  expect(screen.getByText("现在还在继续推进，因为今天这条还剩 2 步没做完。")).toBeInTheDocument();
  expect(screen.getByText("刚刚推进了一步")).toBeInTheDocument();
  expect(screen.getByText("为什么现在做: 今天计划已经排到这一步，需要先把当前小步走完。")).toBeInTheDocument();
  expect(screen.getByText("刚刚做了什么: 推进了计划步骤：把「整理今天的对话记忆」的轮廓理一下")).toBeInTheDocument();
  expect(screen.getByText("产生了什么变化: 今天计划已完成 1/2 步。")).toBeInTheDocument();
  expect(screen.getAllByText("待处理")).toHaveLength(2);
  expect(screen.getByText("把「整理今天的对话记忆」的轮廓理一下")).toBeInTheDocument();
  expect(screen.getByText("开始动手推进")).toBeInTheDocument();
});


test("renders completed state when today's plan is finished", () => {
  render(
    <StatusPanel
      error=""
      focusGoalTitle="整理今天的对话记忆"
      state={{
        mode: "awake",
        focus_mode: "autonomy",
        current_thought: "今天的计划先收住了。",
        active_goal_ids: ["goal-1"],
        focus_effort: {
          goal_id: "goal-1",
          goal_title: "整理今天的对话记忆",
          why_now: "今天计划里的动作已经完成，需要先看结果。",
          action_kind: "command",
          did_what: "执行了命令 `pwd`。",
          effect: "拿到了结果：/Users/ldy/Desktop/map/ai",
          next_hint: "接下来会根据这次执行结果决定下一步。",
          created_at: "2026-04-18T06:30:00.000Z",
        },
        last_action: {
          command: "pwd",
          output: "/Users/ldy/Desktop/map/ai",
        },
        today_plan: {
          goal_id: "goal-1",
          goal_title: "整理今天的对话记忆",
          steps: [
            { content: "把「整理今天的对话记忆」的轮廓理一下", status: "completed" },
            { content: "开始动手推进", status: "completed" },
          ],
        },
      }}
    />
  );

  expect(screen.getByText("当前日程与运行状态")).toBeInTheDocument();
  expect(screen.getAllByText("已完成").length).toBeGreaterThanOrEqual(1);
  expect(screen.getByText("刚刚为焦点执行了动作")).toBeInTheDocument();
  expect(screen.getByText("把「整理今天的对话记忆」的轮廓理一下")).toBeInTheDocument();
  expect(screen.getByText("开始动手推进")).toBeInTheDocument();
});


test("renders relationship state when relationship summary is available", async () => {
  fetchEmotionState.mockResolvedValue({
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

  fetchMemorySummary.mockResolvedValue({
    total_estimated: 24,
    by_kind: { episodic: 6, semantic: 4 },
    recent_count: 3,
    strong_memories: 2,
    relationship: {
      available: true,
      boundaries: ["别替我替你做决定，希望先一起把方案想清楚"],
      commitments: ["答应你重要决定前先给出利弊分析"],
      preferences: ["更喜欢先讨论再执行"],
    },
    available: true,
  });

  render(
    <StatusPanel
      error=""
      state={{
        mode: "awake",
        focus_mode: "autonomy",
        current_thought: "我在整理今天的关系上下文。",
        active_goal_ids: [],
        last_action: null,
        today_plan: null,
      }}
    />
  );

  await waitFor(() => {
    expect(screen.getByText("关系状态")).toBeInTheDocument();
  });
  expect(screen.getByText("相处边界")).toBeInTheDocument();
  expect(screen.getByText("别替我替你做决定，希望先一起把方案想清楚")).toBeInTheDocument();
  expect(screen.getByText("对用户承诺")).toBeInTheDocument();
  expect(screen.getByText("答应你重要决定前先给出利弊分析")).toBeInTheDocument();
  expect(screen.getByText("用户偏好")).toBeInTheDocument();
  expect(screen.getByText("更喜欢先讨论再执行")).toBeInTheDocument();
});

test("compact variant keeps today plan visible and skips secondary insight fetches", () => {
  render(
    <StatusPanel
      error=""
      focusGoalTitle="收敛默认首页"
      focusContext={{
        goal_title: "收敛默认首页",
        source_kind: "goal_chain",
        source_label: "她一直接着往下推进的这条线",
        reason_kind: "goal_chain_continuing",
        reason_label: "这条线已经推到第2步了，还会继续往下走",
        prompt_summary: "当前焦点来自她一直接着往下推进的这条线，之所以还在推进，是因为这条线已经推到第2步了，还会继续往下走。",
      }}
      variant="compact"
      state={{
        mode: "awake",
        focus_mode: "morning_plan",
        current_thought: "先保留主链路。",
        active_goal_ids: ["goal-1"],
        last_action: null,
        today_plan: {
          goal_id: "goal-1",
          goal_title: "收敛默认首页",
          steps: [{ content: "删掉重型默认挂载", status: "pending" }],
        },
      }}
    />
  );

  expect(screen.getByText("当前焦点")).toBeInTheDocument();
  expect(screen.getAllByText("收敛默认首页").length).toBeGreaterThanOrEqual(2);
  expect(screen.getByText("续推中")).toBeInTheDocument();
  expect(screen.getByText("会先盯着这件事，因为这是她一直接着往下推进的这条线。")).toBeInTheDocument();
  expect(fetchEmotionState).not.toHaveBeenCalled();
  expect(fetchMemorySummary).not.toHaveBeenCalled();
  expect(subscribeAppRealtime).not.toHaveBeenCalled();
});

test("updates relationship state from realtime memory events", async () => {
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
    <StatusPanel
      error=""
      state={{
        mode: "awake",
        focus_mode: "autonomy",
        current_thought: "我在留意关系有没有新的变化。",
        active_goal_ids: [],
        last_action: null,
        today_plan: null,
      }}
    />
  );

  await waitFor(() => {
    expect(subscribeAppRealtime).toHaveBeenCalled();
  });

  await act(async () => {
    listener?.({
      type: "memory_updated",
      payload: {
        summary: {
          total_estimated: 12,
          by_kind: {},
          recent_count: 2,
          strong_memories: 1,
          relationship: {
            available: true,
            boundaries: ["别绕开问题，直接告诉我真实判断"],
            commitments: ["答应你遇到风险先提醒再行动"],
            preferences: ["喜欢结论前先看到理由"],
          },
          available: true,
        },
        relationship: {
          available: true,
          boundaries: ["别绕开问题，直接告诉我真实判断"],
          commitments: ["答应你遇到风险先提醒再行动"],
          preferences: ["喜欢结论前先看到理由"],
        },
        timeline: [],
      },
    });
  });

  await waitFor(() => {
    expect(screen.getByText("别绕开问题，直接告诉我真实判断")).toBeInTheDocument();
  });
  expect(screen.getByText("答应你遇到风险先提醒再行动")).toBeInTheDocument();
  expect(screen.getByText("喜欢结论前先看到理由")).toBeInTheDocument();
});
