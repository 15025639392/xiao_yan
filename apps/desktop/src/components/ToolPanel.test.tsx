import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, vi } from "vitest";

const {
  fetchTools,
  fetchToolsStatus,
  fetchConfig,
  fetchChatSkills,
} = vi.hoisted(() => ({
  fetchTools: vi.fn(),
  fetchToolsStatus: vi.fn(),
  fetchConfig: vi.fn(),
  fetchChatSkills: vi.fn(),
}));

vi.mock("../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../lib/api")>("../lib/api");
  return {
    ...actual,
    fetchTools,
    fetchToolsStatus,
    fetchConfig,
    fetchChatSkills,
  };
});

import { ToolPanel } from "./ToolPanel";

beforeEach(() => {
  fetchTools.mockReset();
  fetchToolsStatus.mockReset();
  fetchConfig.mockReset();
  fetchChatSkills.mockReset();

  fetchTools.mockResolvedValue({ by_category: {}, tools: [] });
  fetchToolsStatus.mockResolvedValue({
    statistics: {
      total_executions: 0,
      success_rate: 1,
      failed_count: 0,
      timeout_count: 0,
    },
    safety_filter: "strict",
    allowed_command_count: 0,
    working_directory: "/tmp",
    timeout_seconds: 30,
    sandbox_enabled: true,
    history_size: 0,
    recently_used_tools: [],
  });
  fetchConfig.mockResolvedValue({
    chat_mcp_enabled: false,
    chat_mcp_servers: [],
  });
  fetchChatSkills.mockResolvedValue({ skills: [] });
});

test("renders files as the only default tool tab", async () => {
  render(<ToolPanel />);

  expect(screen.getByRole("tab", { name: "📁 文件" })).toBeInTheDocument();
  expect(screen.queryByRole("tab", { name: "⚡ 执行" })).not.toBeInTheDocument();
  expect(screen.queryByRole("tab", { name: "📋 工具" })).not.toBeInTheDocument();
  expect(screen.queryByRole("tab", { name: "🧠 能力" })).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "能力详情" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "能力目录" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "状态概览" })).toBeInTheDocument();
  expect(fetchTools).not.toHaveBeenCalled();
});

test("loads status lazily when opening the secondary status view", async () => {
  render(<ToolPanel initialTab="files" />);

  expect(fetchToolsStatus).not.toHaveBeenCalled();

  fireEvent.click(screen.getByRole("button", { name: "状态概览" }));

  await waitFor(() => {
    expect(fetchToolsStatus).toHaveBeenCalledTimes(1);
  });
  expect(await screen.findByText("总执行次数")).toBeInTheDocument();
});
