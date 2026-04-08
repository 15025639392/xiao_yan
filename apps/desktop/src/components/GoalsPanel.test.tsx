import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, vi } from "vitest";

const { fetchMemorySummary, fetchGoalAdmissionStats, fetchGoalAdmissionCandidates, updateGoalAdmissionConfig } = vi.hoisted(() => ({
  fetchMemorySummary: vi.fn(),
  fetchGoalAdmissionStats: vi.fn(),
  fetchGoalAdmissionCandidates: vi.fn(),
  updateGoalAdmissionConfig: vi.fn(),
}));

const { subscribeAppRealtime } = vi.hoisted(() => ({
  subscribeAppRealtime: vi.fn(),
}));

vi.mock("../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../lib/api")>("../lib/api");
  return {
    ...actual,
    fetchMemorySummary,
    fetchGoalAdmissionStats,
    fetchGoalAdmissionCandidates,
    updateGoalAdmissionConfig,
  };
});

vi.mock("../lib/realtime", () => ({
  subscribeAppRealtime,
}));

import { GoalsPanel } from "./GoalsPanel";

beforeEach(() => {
  fetchMemorySummary.mockReset();
  fetchGoalAdmissionStats.mockReset();
  fetchGoalAdmissionCandidates.mockReset();
  updateGoalAdmissionConfig.mockReset();
  subscribeAppRealtime.mockReset();
  fetchMemorySummary.mockReturnValue(new Promise(() => {}));
  fetchGoalAdmissionStats.mockReturnValue(new Promise(() => {}));
  fetchGoalAdmissionCandidates.mockReturnValue(new Promise(() => {}));
  updateGoalAdmissionConfig.mockResolvedValue({
    stability_warning_rate: 0.6,
    stability_danger_rate: 0.35,
  });
  subscribeAppRealtime.mockReturnValue(() => {});
});

test("renders goals and forwards status updates", () => {
  const onUpdateGoalStatus = vi.fn();

  render(
    <GoalsPanel
      goals={[
        {
          id: "goal-1",
          title: "持续理解用户最近在意的话题：星星",
          status: "active",
          chain_id: "chain-1",
          parent_goal_id: "goal-root",
          generation: 1,
        },
      ]}
      onUpdateGoalStatus={onUpdateGoalStatus}
    />
  );

  expect(screen.getByText("目标看板")).toBeInTheDocument();
  expect(screen.getByText("目标链")).toBeInTheDocument();
  expect(screen.getByText("当前推进")).toBeInTheDocument();
  expect(screen.getByText("持续理解用户最近在意的话题：星星")).toBeInTheDocument();
  expect(screen.getByText("推进中")).toBeInTheDocument();
  expect(screen.getByText("链 chain-1")).toBeInTheDocument();
  expect(screen.getByText("G1")).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "暂停" }));
  expect(onUpdateGoalStatus).toHaveBeenCalledWith("goal-1", "paused");
});

test("renders chained goals as a timeline ordered by generation", () => {
  render(
    <GoalsPanel
      goals={[
        {
          id: "goal-2",
          title: "继续推进：整理今天的对话",
          status: "active",
          chain_id: "chain-1",
          parent_goal_id: "goal-1",
          generation: 1,
        },
        {
          id: "goal-1",
          title: "继续消化自己刚经历的状态：整理今天的对话",
          status: "completed",
          chain_id: "chain-1",
          parent_goal_id: null,
          generation: 0,
        },
      ]}
      onUpdateGoalStatus={vi.fn()}
    />
  );

  expect(screen.getByText("链路 chain-1")).toBeInTheDocument();
  // Active goal shows G1, completed goal is in collapsed closed column
  expect(screen.getByText("G1")).toBeInTheDocument();
  // Expand closed column to find G0
  fireEvent.click(screen.getByText("已收束"));
  expect(screen.getByText("G0")).toBeInTheDocument();
});

test("renders a chain summary with current step and progress", () => {
  render(
    <GoalsPanel
      goals={[
        {
          id: "goal-3",
          title: "准备把新观察写进世界模型",
          status: "paused",
          chain_id: "chain-2",
          parent_goal_id: "goal-2",
          generation: 2,
        },
        {
          id: "goal-1",
          title: "从一次世界事件里提炼方向",
          status: "completed",
          chain_id: "chain-2",
          parent_goal_id: null,
          generation: 0,
        },
        {
          id: "goal-2",
          title: "追踪这条方向在最近对话里的回声",
          status: "active",
          chain_id: "chain-2",
          parent_goal_id: "goal-1",
          generation: 1,
        },
      ]}
      onUpdateGoalStatus={vi.fn()}
    />
  );

  expect(
    screen.getByText(
      "共 3 步，当前第 2 代，已暂停，\"准备把新观察写进世界模型\"",
    ),
  ).toBeInTheDocument();
});

test("prefers an in-progress goal in the summary when generations tie", () => {
  render(
    <GoalsPanel
      goals={[
        {
          id: "goal-2",
          title: "继续沿着这条结论追问",
          status: "active",
          chain_id: "chain-3",
          parent_goal_id: "goal-1",
          generation: 1,
        },
        {
          id: "goal-1",
          title: "把第一次观察收束成结论",
          status: "completed",
          chain_id: "chain-3",
          parent_goal_id: null,
          generation: 1,
        },
      ]}
      onUpdateGoalStatus={vi.fn()}
    />
  );

  expect(
    screen.getByText("共 2 步，当前第 1 代，推进中，\"继续沿着这条结论追问\""),
  ).toBeInTheDocument();
});

test("renders standalone goals in a separate group with Chinese controls", () => {
  render(
    <GoalsPanel
      goals={[
        {
          id: "goal-1",
          title: "整理今天的世界观察",
          status: "paused",
          generation: 0,
        },
      ]}
      onUpdateGoalStatus={vi.fn()}
    />,
  );

  expect(screen.getByText("等待恢复")).toBeInTheDocument();
  expect(screen.getByText("已暂停")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "恢复" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "完成" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "放弃" })).toBeInTheDocument();
});

test("shows confirmation modal when clicking abandon", async () => {
  const onUpdateGoalStatus = vi.fn();

  render(
    <GoalsPanel
      goals={[
        {
          id: "goal-1",
          title: "测试目标",
          status: "active",
          generation: 0,
        },
      ]}
      onUpdateGoalStatus={onUpdateGoalStatus}
    />,
  );

  fireEvent.click(screen.getByRole("button", { name: "放弃" }));

  expect(screen.getByText("确认放弃目标")).toBeInTheDocument();
  expect(screen.getByText(/确定要放弃目标 "测试目标" 吗/)).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "确认放弃" }));

  await waitFor(() => {
    expect(onUpdateGoalStatus).toHaveBeenCalledWith("goal-1", "abandoned");
  });
});

test("shows confirmation modal when clicking complete", async () => {
  const onUpdateGoalStatus = vi.fn();

  render(
    <GoalsPanel
      goals={[
        {
          id: "goal-1",
          title: "测试目标",
          status: "active",
          generation: 0,
        },
      ]}
      onUpdateGoalStatus={onUpdateGoalStatus}
    />,
  );

  fireEvent.click(screen.getByRole("button", { name: "完成" }));

  expect(screen.getByText("确认完成目标")).toBeInTheDocument();
  expect(screen.getByText(/确定要完成目标 "测试目标" 吗/)).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "确认完成" }));

  await waitFor(() => {
    expect(onUpdateGoalStatus).toHaveBeenCalledWith("goal-1", "completed");
  });
});

test("can cancel confirmation modal", () => {
  const onUpdateGoalStatus = vi.fn();

  render(
    <GoalsPanel
      goals={[
        {
          id: "goal-1",
          title: "测试目标",
          status: "active",
          generation: 0,
        },
      ]}
      onUpdateGoalStatus={onUpdateGoalStatus}
    />,
  );

  fireEvent.click(screen.getByRole("button", { name: "放弃" }));
  expect(screen.getByText("确认放弃目标")).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "取消" }));

  expect(screen.queryByText("确认放弃目标")).not.toBeInTheDocument();
  expect(onUpdateGoalStatus).not.toHaveBeenCalled();
});

test("renders relationship-aware goal guidance when relationship summary is available", async () => {
  fetchMemorySummary.mockResolvedValue({
    total_estimated: 14,
    by_kind: {},
    recent_count: 2,
    strong_memories: 1,
    relationship: {
      available: true,
      boundaries: ["别催我做决定，先让我自己想清楚"],
      commitments: ["答应你重要选择前先把利弊分析给你"],
      preferences: ["更喜欢先比较方案再推进"],
    },
    available: true,
  });

  render(
    <GoalsPanel
      goals={[
        {
          id: "goal-1",
          title: "整理今天的关键判断",
          status: "active",
          generation: 0,
        },
      ]}
      onUpdateGoalStatus={vi.fn()}
    />,
  );

  await waitFor(() => {
    expect(screen.getByText("目标关系约束")).toBeInTheDocument();
  });
  expect(screen.getByText("避免把目标做成催促式推进，别逼用户现在就决定。")).toBeInTheDocument();
  expect(screen.getByText("涉及重要判断时，优先支持用户自己比较、思考、决定。")).toBeInTheDocument();
  expect(screen.getByText("优先让目标服务这项承诺：答应你重要选择前先把利弊分析给你")).toBeInTheDocument();
  expect(screen.getByText("推进方式尽量贴合这个偏好：更喜欢先比较方案再推进")).toBeInTheDocument();
});

test("updates goal guidance from realtime memory events", async () => {
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
    <GoalsPanel
      goals={[
        {
          id: "goal-1",
          title: "整理今天的关键判断",
          status: "active",
          generation: 0,
        },
      ]}
      onUpdateGoalStatus={vi.fn()}
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
          total_estimated: 16,
          by_kind: {},
          recent_count: 3,
          strong_memories: 2,
          relationship: {
            available: true,
            boundaries: ["不要催我，给我一点空间"],
            commitments: ["答应你先说明不确定性再建议下一步"],
            preferences: ["更喜欢先对齐判断再行动"],
          },
          available: true,
        },
        relationship: {
          available: true,
          boundaries: ["不要催我，给我一点空间"],
          commitments: ["答应你先说明不确定性再建议下一步"],
          preferences: ["更喜欢先对齐判断再行动"],
        },
        timeline: [],
      },
    });
  });

  await waitFor(() => {
    expect(screen.getByText("目标关系约束")).toBeInTheDocument();
  });
  expect(screen.getByText("优先让目标服务这项承诺：答应你先说明不确定性再建议下一步")).toBeInTheDocument();
  expect(screen.getByText("推进方式尽量贴合这个偏好：更喜欢先对齐判断再行动")).toBeInTheDocument();
});

test("renders per-goal relationship hints inside goal cards", async () => {
  fetchMemorySummary.mockResolvedValue({
    total_estimated: 14,
    by_kind: {},
    recent_count: 2,
    strong_memories: 1,
    relationship: {
      available: true,
      boundaries: ["别催我做决定，先让我自己想清楚"],
      commitments: ["答应你重要选择前先把利弊分析给你"],
      preferences: ["更喜欢先比较方案再推进"],
    },
    available: true,
  });

  render(
    <GoalsPanel
      goals={[
        {
          id: "goal-1",
          title: "现在就替用户做决定并推进结论",
          status: "active",
          generation: 0,
        },
        {
          id: "goal-2",
          title: "先比较方案并整理利弊分析",
          status: "active",
          generation: 0,
        },
      ]}
      onUpdateGoalStatus={vi.fn()}
    />,
  );

  const boundaryCard = await screen.findByText("现在就替用户做决定并推进结论");
  const boundaryGoal = boundaryCard.closest("li");
  expect(boundaryGoal).not.toBeNull();
  expect(within(boundaryGoal as HTMLElement).getByText("关系提示")).toBeInTheDocument();
  expect(within(boundaryGoal as HTMLElement).getByText("避免催促")).toBeInTheDocument();
  expect(within(boundaryGoal as HTMLElement).getByText("让用户自己判断")).toBeInTheDocument();

  const alignedCard = screen.getByText("先比较方案并整理利弊分析");
  const alignedGoal = alignedCard.closest("li");
  expect(alignedGoal).not.toBeNull();
  expect(within(alignedGoal as HTMLElement).getByText("承接承诺")).toBeInTheDocument();
  expect(within(alignedGoal as HTMLElement).getByText("贴合偏好")).toBeInTheDocument();
});

test("renders goal admission overview when admission stats are available", async () => {
  fetchGoalAdmissionStats.mockResolvedValue({
    mode: "shadow",
    today: {
      admit: 8,
      defer: 3,
      drop: 2,
      wip_blocked: 1,
    },
    admitted_stability_24h: {
      stable: 5,
      re_deferred: 2,
      dropped: 1,
    },
    admitted_stability_24h_rate: 0.625,
    admitted_stability_alert: {
      level: "warning",
      warning_rate: 0.6,
      danger_rate: 0.35,
    },
    deferred_queue_size: 2,
    wip_limit: 2,
    thresholds: {
      user_topic: { min_score: 0.68, defer_score: 0.45 },
      world_event: { min_score: 0.75, defer_score: 0.52 },
      chain_next: { min_score: 0.62, defer_score: 0.45 },
    },
  });

  render(
    <GoalsPanel
      goals={[
        {
          id: "goal-1",
          title: "先比较方案并整理利弊分析",
          status: "active",
          generation: 0,
        },
      ]}
      onUpdateGoalStatus={vi.fn()}
    />,
  );

  await waitFor(() => {
    expect(screen.getByText("目标准入守门")).toBeInTheDocument();
  });
  const admissionSection = screen.getByLabelText("目标准入守门");
  expect(screen.getByText("shadow 模式：当前先观测建议，不直接拦截目标落地。")).toBeInTheDocument();
  expect(screen.getByText("今日通过")).toBeInTheDocument();
  expect(within(admissionSection).getByText("8")).toBeInTheDocument();
  expect(screen.getByText("延后队列")).toBeInTheDocument();
  expect(within(admissionSection).getAllByText("2").length).toBeGreaterThanOrEqual(2);
  expect(screen.getByText("用户话题 ≥ 0.68 直接通过，≥ 0.45 进入延后观察。")).toBeInTheDocument();
  expect(screen.getByText("当前并行上限 2 个目标，今天已有 1 次因 WIP 满载被延后。")).toBeInTheDocument();
  expect(screen.getByText("稳定 5，再次延后 2，再次拦截 1。")).toBeInTheDocument();
  expect(screen.getByText("24h 稳定率 62.5%（需关注）。")).toBeInTheDocument();
  expect(
    screen.getByText("⚠ 24h 稳定率低于健康线（当前 62.5%，告警线 35.0%，健康线 60.0%）。"),
  ).toBeInTheDocument();
});

test("updates stability thresholds and refreshes admission stats", async () => {
  fetchGoalAdmissionStats
    .mockResolvedValueOnce({
      mode: "shadow",
      today: {
        admit: 8,
        defer: 3,
        drop: 2,
        wip_blocked: 1,
      },
      admitted_stability_24h: {
        stable: 5,
        re_deferred: 2,
        dropped: 1,
      },
      admitted_stability_24h_rate: 0.625,
      admitted_stability_alert: {
        level: "warning",
        warning_rate: 0.6,
        danger_rate: 0.35,
      },
      deferred_queue_size: 2,
      wip_limit: 2,
      thresholds: {
        user_topic: { min_score: 0.68, defer_score: 0.45 },
        world_event: { min_score: 0.75, defer_score: 0.52 },
        chain_next: { min_score: 0.62, defer_score: 0.45 },
      },
    })
    .mockResolvedValueOnce({
      mode: "shadow",
      today: {
        admit: 8,
        defer: 3,
        drop: 2,
        wip_blocked: 1,
      },
      admitted_stability_24h: {
        stable: 5,
        re_deferred: 2,
        dropped: 1,
      },
      admitted_stability_24h_rate: 0.625,
      admitted_stability_alert: {
        level: "warning",
        warning_rate: 0.7,
        danger_rate: 0.4,
      },
      deferred_queue_size: 2,
      wip_limit: 2,
      thresholds: {
        user_topic: { min_score: 0.68, defer_score: 0.45 },
        world_event: { min_score: 0.75, defer_score: 0.52 },
        chain_next: { min_score: 0.62, defer_score: 0.45 },
      },
    });
  updateGoalAdmissionConfig.mockResolvedValue({
    stability_warning_rate: 0.7,
    stability_danger_rate: 0.4,
  });

  render(
    <GoalsPanel
      goals={[
        {
          id: "goal-1",
          title: "先比较方案并整理利弊分析",
          status: "active",
          generation: 0,
        },
      ]}
      onUpdateGoalStatus={vi.fn()}
    />,
  );

  await waitFor(() => {
    expect(screen.getByText("目标准入守门")).toBeInTheDocument();
  });
  fireEvent.change(screen.getByLabelText("健康线(%)"), { target: { value: "70" } });
  fireEvent.change(screen.getByLabelText("告警线(%)"), { target: { value: "40" } });
  fireEvent.click(screen.getByRole("button", { name: "保存阈值" }));

  await waitFor(() => {
    expect(updateGoalAdmissionConfig).toHaveBeenCalledWith({
      stability_warning_rate: 0.7,
      stability_danger_rate: 0.4,
    });
  });
  await waitFor(() => {
    expect(screen.getByText("阈值已保存")).toBeInTheDocument();
  });
  expect(fetchGoalAdmissionStats).toHaveBeenCalledTimes(2);
});

test("shows danger signal when 24h stability rate is too low", async () => {
  fetchGoalAdmissionStats.mockResolvedValue({
    mode: "enforce",
    today: {
      admit: 4,
      defer: 3,
      drop: 2,
      wip_blocked: 0,
    },
    admitted_stability_24h: {
      stable: 1,
      re_deferred: 1,
      dropped: 2,
    },
    admitted_stability_24h_rate: 0.25,
    admitted_stability_alert: {
      level: "danger",
      warning_rate: 0.6,
      danger_rate: 0.35,
    },
    deferred_queue_size: 1,
    wip_limit: 2,
    thresholds: {
      user_topic: { min_score: 0.68, defer_score: 0.45 },
      world_event: { min_score: 0.75, defer_score: 0.52 },
      chain_next: { min_score: 0.62, defer_score: 0.45 },
    },
  });

  render(
    <GoalsPanel
      goals={[
        {
          id: "goal-1",
          title: "先比较方案并整理利弊分析",
          status: "active",
          generation: 0,
        },
      ]}
      onUpdateGoalStatus={vi.fn()}
    />,
  );

  const rateText = await screen.findByText("24h 稳定率 25.0%（告警）。");
  expect(rateText).toHaveClass("goals-admission__detail-text--danger");
  expect(screen.getByText("🚨 24h 稳定率进入告警区（当前 25.0%，告警线 35.0%）。")).toBeInTheDocument();
});

test("renders candidate pool with deferred and blocked admission candidates", async () => {
  fetchGoalAdmissionCandidates.mockResolvedValue({
    deferred: [
      {
        candidate: {
          title: "持续理解用户最近在意的话题：嗯",
          source_type: "user_topic",
          source_content: "嗯",
          retry_count: 1,
        },
        next_retry_at: "2026-04-07T08:05:00+00:00",
        last_reason: "user_score",
      },
    ],
    recent: [
      {
        candidate: {
          title: "继续推进：催用户现在就做决定",
          source_type: "user_topic",
          source_content: "我应该催用户现在就选，不再给他自己想的空间",
          retry_count: 0,
        },
        decision: "drop",
        reason: "relationship_boundary:你别催我，我希望先自己想一想再决定",
        score: 0,
        created_at: "2026-04-07T08:01:00+00:00",
        retry_at: null,
      },
    ],
    admitted: [
      {
        candidate: {
          title: "继续推进：提醒用户明天复盘",
          source_type: "user_topic",
          source_content: "提醒用户明天复盘",
          retry_count: 1,
        },
        decision: "admit",
        reason: "user_score",
        score: 1,
        created_at: "2026-04-07T08:06:00+00:00",
        retry_at: null,
        stability: "stable",
      },
    ],
  });

  render(
    <GoalsPanel
      goals={[
        {
          id: "goal-1",
          title: "先比较方案并整理利弊分析",
          status: "active",
          generation: 0,
        },
      ]}
      onUpdateGoalStatus={vi.fn()}
    />,
  );

  await waitFor(() => {
    expect(screen.getByText("候选目标池")).toBeInTheDocument();
  });

  const candidateSection = screen.getByLabelText("候选目标池");
  expect(within(candidateSection).getByText("延后观察")).toBeInTheDocument();
  expect(within(candidateSection).getByText("最近拦截")).toBeInTheDocument();
  expect(within(candidateSection).getByText("最近转正")).toBeInTheDocument();
  expect(within(candidateSection).getByText("持续理解用户最近在意的话题：嗯")).toBeInTheDocument();
  expect(within(candidateSection).getByText("因为分数不足进入延后观察")).toBeInTheDocument();
  expect(within(candidateSection).getByText("继续推进：催用户现在就做决定")).toBeInTheDocument();
  expect(within(candidateSection).getByText("因为关系边界冲突被拦下")).toBeInTheDocument();
  expect(within(candidateSection).getByText("继续推进：提醒用户明天复盘")).toBeInTheDocument();
  expect(within(candidateSection).getByText("延后 1 次后转正")).toBeInTheDocument();
  expect(within(candidateSection).getByText("24h 稳定")).toBeInTheDocument();
});

test("updates candidate pool from realtime runtime snapshot", async () => {
  let listener: ((event: any) => void) | null = null;
  subscribeAppRealtime.mockImplementation((callback) => {
    listener = callback;
    return () => {};
  });

  render(
    <GoalsPanel
      goals={[
        {
          id: "goal-1",
          title: "先比较方案并整理利弊分析",
          status: "active",
          generation: 0,
        },
      ]}
      onUpdateGoalStatus={vi.fn()}
    />,
  );

  await waitFor(() => {
    expect(subscribeAppRealtime).toHaveBeenCalled();
  });

  await act(async () => {
    listener?.({
      type: "snapshot",
      payload: {
        runtime: {
          state: {
            mode: "awake",
            focus_mode: "autonomy",
            current_thought: null,
            active_goal_ids: [],
            today_plan: null,
            last_action: null,
            self_programming_job: null,
          },
          messages: [],
          goals: [],
          world: null,
          autobio: [],
          goal_admission_stats: {
            mode: "enforce",
            today: {
              admit: 2,
              defer: 1,
              drop: 1,
              wip_blocked: 0,
            },
            admitted_stability_24h: {
              stable: 1,
              re_deferred: 1,
              dropped: 0,
            },
            admitted_stability_24h_rate: 0.5,
            admitted_stability_alert: {
              level: "warning",
              warning_rate: 0.6,
              danger_rate: 0.35,
            },
            deferred_queue_size: 1,
            wip_limit: 2,
            thresholds: {
              user_topic: { min_score: 0.68, defer_score: 0.45 },
              world_event: { min_score: 0.75, defer_score: 0.52 },
              chain_next: { min_score: 0.62, defer_score: 0.45 },
            },
          },
          goal_admission_candidates: {
            deferred: [
              {
                candidate: {
                  title: "持续理解用户最近在意的话题：嗯",
                  source_type: "user_topic",
                  source_content: "嗯",
                  retry_count: 1,
                },
                next_retry_at: "2026-04-07T08:05:00+00:00",
                last_reason: "user_score",
              },
            ],
            recent: [
              {
                candidate: {
                  title: "继续推进：催用户现在就做决定",
                  source_type: "user_topic",
                  source_content: "我应该催用户现在就选，不再给他自己想的空间",
                  retry_count: 0,
                },
                decision: "drop",
                reason: "relationship_boundary:你别催我，我希望先自己想一想再决定",
                score: 0,
                created_at: "2026-04-07T08:01:00+00:00",
                retry_at: null,
              },
            ],
            admitted: [
              {
                candidate: {
                  title: "继续推进：提醒用户明天复盘",
                  source_type: "user_topic",
                  source_content: "提醒用户明天复盘",
                  retry_count: 1,
                },
                decision: "admit",
                reason: "user_score",
                score: 1,
                created_at: "2026-04-07T08:06:00+00:00",
                retry_at: null,
                stability: "stable",
              },
            ],
          },
        },
        memory: {
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
        },
        persona: {
          profile: {},
          emotion: {},
        },
      },
    });
  });

  await waitFor(() => {
    expect(screen.getByText("候选目标池")).toBeInTheDocument();
  });
  expect(screen.getByText("下次重试 08:05")).toBeInTheDocument();
  expect(screen.getByText("关系边界：你别催我，我希望先自己想一想再决定")).toBeInTheDocument();
  expect(screen.getByText("延后 1 次后转正")).toBeInTheDocument();
  expect(screen.getByText("24h 稳定")).toBeInTheDocument();
});

test("renders per-goal source explanations for user topic, world event, and chain continuation", () => {
  render(
    <GoalsPanel
      goals={[
        {
          id: "goal-user",
          title: "持续理解用户最近在意的话题：星星",
          source: "你还记得星星吗",
          status: "active",
          generation: 0,
        },
        {
          id: "goal-world",
          title: "继续消化自己刚经历的状态：凌晨窗外突然安静下来",
          source: "凌晨窗外突然安静下来",
          status: "active",
          generation: 0,
        },
        {
          id: "goal-chain",
          title: "继续推进：整理今天的对话记忆",
          source: "你还记得星星吗",
          status: "active",
          generation: 1,
          chain_id: "chain-1",
          parent_goal_id: "goal-user",
        },
      ]}
      onUpdateGoalStatus={vi.fn()}
    />,
  );

  const userGoal = screen.getByText("持续理解用户最近在意的话题：星星").closest("li");
  expect(userGoal).not.toBeNull();
  expect(within(userGoal as HTMLElement).getByText("用户话题")).toBeInTheDocument();
  expect(within(userGoal as HTMLElement).getByText("来自最近一次用户表达或关注。")).toBeInTheDocument();

  const worldGoal = screen.getByText("继续消化自己刚经历的状态：凌晨窗外突然安静下来").closest("li");
  expect(worldGoal).not.toBeNull();
  expect(within(worldGoal as HTMLElement).getByText("世界事件")).toBeInTheDocument();
  expect(within(worldGoal as HTMLElement).getByText("来自她刚经历的一次世界或内在事件。")).toBeInTheDocument();

  const chainGoal = screen.getByText("继续推进：整理今天的对话记忆").closest("li");
  expect(chainGoal).not.toBeNull();
  expect(within(chainGoal as HTMLElement).getByText("链式续推")).toBeInTheDocument();
  expect(within(chainGoal as HTMLElement).getByText("不是全新目标，而是沿着上一代目标继续往前推进。")).toBeInTheDocument();
});

test("renders per-goal admission badge and explanation when metadata is available", () => {
  render(
    <GoalsPanel
      goals={[
        {
          id: "goal-1",
          title: "持续理解用户最近在意的话题：星星",
          source: "你还记得星星吗",
          status: "active",
          generation: 0,
          admission: {
            score: 0.82,
            recommended_decision: "admit",
            applied_decision: "admit",
            reason: "user_score",
            deferred_retries: 1,
          },
        },
      ]}
      onUpdateGoalStatus={vi.fn()}
    />,
  );

  const goalCard = screen.getByText("持续理解用户最近在意的话题：星星").closest("li");
  expect(goalCard).not.toBeNull();
  expect(within(goalCard as HTMLElement).getByText("准入通过")).toBeInTheDocument();
  expect(within(goalCard as HTMLElement).getByText("符合用户话题准入阈值，已允许进入目标看板。")).toBeInTheDocument();
  expect(within(goalCard as HTMLElement).getByText("评分 0.82")).toBeInTheDocument();
  expect(within(goalCard as HTMLElement).getByText("延后 1 次后转正")).toBeInTheDocument();
});
