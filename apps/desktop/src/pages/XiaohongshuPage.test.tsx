import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { vi } from "vitest";

import { fetchXhsWorkDomain, updateXhsWorkDomain, wakeLifecycle } from "../lib/api";
import { previewXiaohongshuCover } from "../lib/apiXiaohongshu";
import { XiaohongshuPage } from "./XiaohongshuPage";

vi.mock("../lib/tauri/fsAccess", () => ({
  browserOpen: vi.fn(),
}));

vi.mock("../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../lib/api")>("../lib/api");
  return {
    ...actual,
    fetchXhsWorkDomain: vi.fn(),
    updateXhsWorkDomain: vi.fn(),
    wakeLifecycle: vi.fn().mockResolvedValue({
      mode: "awake",
      focus_mode: "autonomy",
      current_thought: null,
    }),
  };
});

vi.mock("../lib/apiXiaohongshu", () => ({
  previewXiaohongshuCover: vi.fn().mockResolvedValue({
    title: "测试标题",
    body: "测试正文",
    template_name: "expert_clean",
    available_templates: ["warm_story", "expert_clean", "bold_hook"],
    image_path: "/tmp/xhs-cover-preview.png",
    image_data_url: "data:image/png;base64,preview-default",
  }),
}));

beforeEach(() => {
  vi.clearAllMocks();
});

test("xiaohongshu page defaults to manual light-science publishing", async () => {
  vi.mocked(fetchXhsWorkDomain).mockResolvedValue({
    available: true,
    profile: {
      work_type: "xiaohongshu_operations",
      account_name: "已登录账号",
      account_positioning: "数字生命式情绪关系轻科普",
      target_audience: "需要被理解的人",
      expression_style: "先接住再解释",
      scouting_interval_hours: 1,
      publish_mode: "manual",
    },
    state: {
      status: "idle",
      current_focus: "",
      backlog_count: 0,
      active_task_ids: [],
      last_published_at: null,
      last_scouting_at: null,
      current_bottleneck: "",
      next_recommended_action: "",
      review_session_id: "",
      pending_drafts: [],
      published_history: [],
    },
    goals: {
      north_star: "",
      weekly_goals: [],
      monthly_content_target: 0,
    },
  });

  render(<XiaohongshuPage assistantName="小晏" />);

  await waitFor(() => {
    expect(screen.getByText("小红书经营闭环")).toBeInTheDocument();
  });
  expect(screen.getByText("手动发布")).toBeInTheDocument();
  expect(screen.queryByText("自动直发")).not.toBeInTheDocument();
});

test("xiaohongshu page can prioritize and publish a non-first pending draft", async () => {
  vi.mocked(fetchXhsWorkDomain).mockResolvedValue({
    available: true,
    profile: {
      work_type: "xiaohongshu_operations",
      account_name: "已登录账号",
      account_positioning: "数字生命式情绪关系轻科普",
      target_audience: "需要被理解的人",
      expression_style: "先接住再解释",
      scouting_interval_hours: 1,
      publish_mode: "manual",
    },
    state: {
      status: "idle",
      current_focus: "",
      backlog_count: 2,
      active_task_ids: [],
      last_published_at: null,
      last_scouting_at: null,
      current_bottleneck: "",
      next_recommended_action: "",
      review_session_id: "",
      pending_drafts: [
        {
          draft_id: "draft-1",
          title: "第一条草稿",
          body: "第一条正文",
          generated_at: "2026-04-23T00:00:00Z",
          status: "pending",
        },
        {
          draft_id: "draft-2",
          title: "第二条草稿",
          body: "第二条正文",
          generated_at: "2026-04-23T00:01:00Z",
          status: "pending",
        },
      ],
      published_history: [],
    },
    goals: {
      north_star: "",
      weekly_goals: [],
      monthly_content_target: 0,
    },
  });
  vi.mocked(updateXhsWorkDomain).mockResolvedValue({ ok: true });

  render(<XiaohongshuPage assistantName="小晏" />);

  await waitFor(() => {
    expect(screen.getByDisplayValue("第一条草稿")).toBeInTheDocument();
    expect(screen.getByDisplayValue("第二条草稿")).toBeInTheDocument();
  });

  fireEvent.click(screen.getAllByRole("button", { name: "发布这条" })[1]!);

  await waitFor(() => {
    expect(updateXhsWorkDomain).toHaveBeenCalledWith(
      expect.objectContaining({
        status: "publishing",
        backlog_count: 2,
        pending_drafts: [
          expect.objectContaining({ draft_id: "draft-2", title: "第二条草稿", body: "第二条正文" }),
          expect.objectContaining({ draft_id: "draft-1", title: "第一条草稿", body: "第一条正文" }),
        ],
      }),
    );
  });
});

test("pending draft list can preview and switch cover templates", async () => {
  const previewMock = vi.mocked(previewXiaohongshuCover);
  previewMock.mockResolvedValueOnce({
    title: "测试标题",
    body: "测试正文",
    template_name: "expert_clean",
    available_templates: ["warm_story", "expert_clean", "bold_hook"],
    image_path: "/tmp/xhs-cover-preview.png",
    image_data_url: "data:image/png;base64,preview-default",
  });
  previewMock.mockResolvedValueOnce({
    title: "测试标题",
    body: "测试正文",
    template_name: "bold_hook",
    available_templates: ["warm_story", "expert_clean", "bold_hook"],
    image_path: "/tmp/xhs-cover-preview-bold.png",
    image_data_url: "data:image/png;base64,preview-bold",
  });

  vi.mocked(fetchXhsWorkDomain).mockResolvedValue({
    available: true,
    profile: {
      work_type: "xiaohongshu_operations",
      account_name: "已登录账号",
      account_positioning: "数字生命式情绪关系轻科普",
      target_audience: "需要被理解的人",
      expression_style: "先接住再解释",
      scouting_interval_hours: 1,
      publish_mode: "manual",
    },
    state: {
      status: "idle",
      current_focus: "",
      backlog_count: 1,
      active_task_ids: [],
      last_published_at: null,
      last_scouting_at: null,
      current_bottleneck: "",
      next_recommended_action: "",
      review_session_id: "",
      pending_drafts: [
        {
          draft_id: "draft-1",
          title: "测试标题",
          body: "测试正文",
          generated_at: "2026-04-23T00:00:00Z",
          status: "pending",
        },
      ],
      published_history: [],
    },
    goals: {
      north_star: "",
      weekly_goals: [],
      monthly_content_target: 0,
    },
  });

  render(<XiaohongshuPage assistantName="小晏" />);

  await waitFor(() => {
    expect(screen.getByAltText("待发布草稿封面-expert_clean")).toBeInTheDocument();
  });
  expect(previewMock).toHaveBeenCalledWith({ title: "测试标题", body: "测试正文" });

  fireEvent.click(screen.getByRole("button", { name: "强钩子" }));

  await waitFor(() => {
    expect(screen.getByAltText("待发布草稿封面-bold_hook")).toBeInTheDocument();
  });
  expect(previewMock).toHaveBeenLastCalledWith({
    title: "测试标题",
    body: "测试正文",
    template_name: "bold_hook",
  });
});

test("xiaohongshu page saves publish mode from config panel", async () => {
  vi.mocked(fetchXhsWorkDomain).mockResolvedValue({
    available: true,
    profile: {
      work_type: "xiaohongshu_operations",
      account_name: "已登录账号",
      account_positioning: "数字生命式情绪关系轻科普",
      target_audience: "需要被理解的人",
      expression_style: "先接住再解释",
      scouting_interval_hours: 1,
      publish_mode: "manual",
    },
    state: {
      status: "idle",
      current_focus: "",
      backlog_count: 0,
      active_task_ids: [],
      last_published_at: null,
      last_scouting_at: null,
      current_bottleneck: "",
      next_recommended_action: "",
      review_session_id: "",
      pending_drafts: [],
      published_history: [],
    },
    goals: {
      north_star: "",
      weekly_goals: [],
      monthly_content_target: 0,
    },
  });
  vi.mocked(updateXhsWorkDomain).mockResolvedValue({ ok: true });

  render(<XiaohongshuPage assistantName="小晏" />);

  await waitFor(() => {
    expect(screen.getByText("小红书经营闭环")).toBeInTheDocument();
  });

  fireEvent.click(screen.getByRole("button", { name: "配置" }));
  fireEvent.change(screen.getByDisplayValue("手动发布"), {
    target: { value: "auto" },
  });
  fireEvent.click(screen.getByRole("button", { name: "保存" }));

  await waitFor(() => {
    expect(updateXhsWorkDomain).toHaveBeenCalledWith(
      expect.objectContaining({
        publish_mode: "auto",
      }),
    );
  });
});
