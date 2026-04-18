import { act, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, vi } from "vitest";

const {
  fetchGoalAdmissionStats,
  fetchGoalAdmissionCandidates,
  fetchGoalAdmissionConfigHistory,
} = vi.hoisted(() => ({
  fetchGoalAdmissionStats: vi.fn(),
  fetchGoalAdmissionCandidates: vi.fn(),
  fetchGoalAdmissionConfigHistory: vi.fn(),
}));

const { subscribeAppRealtime } = vi.hoisted(() => ({
  subscribeAppRealtime: vi.fn(),
}));

vi.mock("../../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../../lib/api")>("../../lib/api");
  return {
    ...actual,
    fetchGoalAdmissionStats,
    fetchGoalAdmissionCandidates,
    fetchGoalAdmissionConfigHistory,
  };
});

vi.mock("../../lib/realtime", () => ({
  subscribeAppRealtime,
}));

import { GoalsGovernanceSection } from "./GoalsGovernanceSection";

beforeEach(() => {
  fetchGoalAdmissionStats.mockReset();
  fetchGoalAdmissionCandidates.mockReset();
  fetchGoalAdmissionConfigHistory.mockReset();
  subscribeAppRealtime.mockReset();
  subscribeAppRealtime.mockReturnValue(() => {});
});

test("renders governance guidance and fetched admission state", async () => {
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
      chain_next: { min_score: 0.62, defer_score: 0.45 },
    },
  });
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
    recent: [],
    admitted: [],
  });
  fetchGoalAdmissionConfigHistory.mockResolvedValue({ items: [] });

  render(
    <GoalsGovernanceSection
      relationship={{
        available: true,
        boundaries: ["别催我做决定，先让我自己想清楚"],
        commitments: ["答应你重要选择前先把利弊分析给你"],
        preferences: ["更喜欢先比较方案再推进"],
      }}
    />,
  );

  await waitFor(() => {
    expect(screen.getByText("目标关系约束")).toBeInTheDocument();
  });
  expect(screen.getByText("避免把目标做成催促式推进，别逼用户现在就决定。")).toBeInTheDocument();
  expect(screen.getByText("目标准入守门")).toBeInTheDocument();
  expect(screen.getByText("shadow 模式：当前先观测建议，不直接拦截目标落地。")).toBeInTheDocument();
  expect(screen.getByText("候选目标池")).toBeInTheDocument();
  expect(screen.getByText("持续理解用户最近在意的话题：嗯")).toBeInTheDocument();
});

test("updates admission cards from realtime runtime payload", async () => {
  fetchGoalAdmissionStats.mockResolvedValue(null);
  fetchGoalAdmissionCandidates.mockResolvedValue({ deferred: [], recent: [], admitted: [] });
  fetchGoalAdmissionConfigHistory.mockResolvedValue({ items: [] });

  let listener: ((event: any) => void) | null = null;
  subscribeAppRealtime.mockImplementation((callback) => {
    listener = callback;
    return () => {};
  });

  render(
    <GoalsGovernanceSection
      relationship={{
        available: false,
        boundaries: [],
        commitments: [],
        preferences: [],
      }}
    />,
  );

  await waitFor(() => {
    expect(subscribeAppRealtime).toHaveBeenCalled();
  });

  await act(async () => {
    listener?.({
      type: "runtime_updated",
      payload: {
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
          admitted: [],
        },
      },
    });
  });

  await waitFor(() => {
    expect(screen.getByText("目标准入守门")).toBeInTheDocument();
  });
  const candidatePool = screen.getByLabelText("候选目标池");
  expect(within(candidatePool).getByText("持续理解用户最近在意的话题：嗯")).toBeInTheDocument();
  expect(within(candidatePool).getByText("因为关系边界冲突被拦下")).toBeInTheDocument();
});
