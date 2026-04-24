import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, test, vi } from "vitest";

import { VrmGenerationPage } from "./VrmGenerationPage";
import * as api from "../lib/apiVrmGeneration";
import * as preview from "../components/avatar/avatarPreviewModel";

beforeEach(() => {
  vi.restoreAllMocks();
});

test("creates a VRM generation job and shows completed artifact", async () => {
  vi.spyOn(api, "createVrmGenerationJob").mockResolvedValue({
    job_id: "job-1",
    prompt: "小晏，白色居家裙",
    status: "queued",
    artifacts: {},
  });
  vi.spyOn(api, "fetchVrmGenerationJob").mockResolvedValue({
    job_id: "job-1",
    prompt: "小晏，白色居家裙",
    status: "completed",
    artifacts: { output_vrm_path: "/tmp/xiaoyan.vrm" },
  });

  render(<VrmGenerationPage assistantName="小晏" pollIntervalMs={1} />);

  fireEvent.change(screen.getByLabelText("形象描述"), { target: { value: "小晏，白色居家裙" } });
  fireEvent.click(screen.getByRole("button", { name: "生成 VRM 草稿" }));

  await waitFor(() => expect(screen.getByText("completed")).toBeInTheDocument());
  expect(screen.getByText("/tmp/xiaoyan.vrm")).toBeInTheDocument();
});


test("loads a completed VRM artifact as current preview only after confirmation", async () => {
  vi.spyOn(api, "createVrmGenerationJob").mockResolvedValue({
    job_id: "job-1",
    prompt: "小晏，白色居家裙",
    status: "queued",
    artifacts: {},
  });
  vi.spyOn(api, "fetchVrmGenerationJob").mockResolvedValue({
    job_id: "job-1",
    prompt: "小晏，白色居家裙",
    status: "completed",
    artifacts: { output_vrm_path: "/tmp/xiaoyan.vrm" },
  });
  const loadPreview = vi.spyOn(preview, "loadAvatarPreviewModel").mockResolvedValue();

  render(<VrmGenerationPage assistantName="小晏" pollIntervalMs={1} />);

  fireEvent.change(screen.getByLabelText("形象描述"), { target: { value: "小晏，白色居家裙" } });
  fireEvent.click(screen.getByRole("button", { name: "生成 VRM 草稿" }));
  await waitFor(() => expect(screen.getByText("/tmp/xiaoyan.vrm")).toBeInTheDocument());

  expect(loadPreview).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: "加载为当前预览模型" }));

  await waitFor(() => expect(loadPreview).toHaveBeenCalledWith("/tmp/xiaoyan.vrm"));
  expect(screen.getByText("已加载到预览窗口，未替换正式形象。")).toBeInTheDocument();
});


test("loads recent generation jobs on mount", async () => {
  vi.spyOn(api, "listVrmGenerationJobs").mockResolvedValue({
    items: [
      {
        job_id: "job-recent",
        prompt: "最近的小晏",
        status: "completed",
        artifacts: { output_vrm_path: "/tmp/recent.vrm" },
      },
    ],
  });

  render(<VrmGenerationPage assistantName="小晏" pollIntervalMs={1} />);

  await waitFor(() => expect(screen.getByText("最近生成")).toBeInTheDocument());
  expect(screen.getByText("最近的小晏")).toBeInTheDocument();
  expect(screen.getByText("/tmp/recent.vrm")).toBeInTheDocument();
});
