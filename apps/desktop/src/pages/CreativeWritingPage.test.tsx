import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import { CreativeWritingPage } from "./CreativeWritingPage";

afterEach(() => {
  vi.restoreAllMocks();
});

function jsonResponse(body: unknown) {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

const project = {
  id: "novel-1",
  title: "雨巷档案",
  premise: "每场雨都会留下一个无人认领的档案袋。",
  tone: "细腻",
  habit_note: "长期创作",
  habit_state: {
    attachment_reason: "她想知道档案袋为什么认识她。",
    last_pause: "停在封蜡。",
    next_intention: "写档案袋里出现童年的地址。",
    cadence_note: "慢慢写。",
    updated_at: "2026-04-28T00:00:00Z",
  },
  current_chapter_index: 1,
  status: "drafting",
  folder_name: "novel-1-rain",
  created_at: "2026-04-28T00:00:00Z",
  updated_at: "2026-04-28T00:00:00Z",
};

function installFetchMock() {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    if (url.endsWith("/creative-writing/projects") && !init) {
      return jsonResponse({ projects: [project] });
    }
    if (url.endsWith("/creative-writing/sessions") && !init) {
      return jsonResponse({
        sessions: [
          {
            id: "session-1",
            project_id: "novel-1",
            title: "雨巷档案",
            intention: "写档案袋里出现童年的地址。",
            suggested_action: "继续写一个短片段",
            reasons: ["下一步明确"],
            context: {
              project_id: "novel-1",
              chapter_index: 1,
              previous_chapter_summaries: [],
              recent_summaries: [],
              recent_excerpt: "雨水把档案袋的边角泡软了。",
            },
            status: "pending",
            completed_fragment_id: null,
            created_at: "2026-04-28T00:00:00Z",
            updated_at: "2026-04-28T00:00:00Z",
          },
        ],
      });
    }
    if (url.endsWith("/creative-writing/impulses")) {
      return jsonResponse({
        recommended_project_id: "novel-1",
        being_context: {
          time_of_day: "night",
          energy: "low",
          mood: "tired",
          focus_tension: "low",
          primary_emotion: "engaged",
          primary_intensity: "moderate",
          mood_valence: 0.2,
          arousal: 0.7,
        },
        impulses: [
          {
            project_id: "novel-1",
            title: "雨巷档案",
            score: 85,
            reasons: ["下一步明确", "此刻能量偏低，更适合轻轻写一个短片段。"],
            next_intention: "写档案袋里出现童年的地址。",
            suggested_action: "继续写一个短片段",
          },
        ],
      });
    }
    if (url.endsWith("/creative-writing/projects/novel-1") && !init) {
      return jsonResponse({
        project,
        fragments: [
          {
            id: "fragment-1",
            project_id: "novel-1",
            chapter_index: 1,
            sequence: 1,
            content: "雨水把档案袋的边角泡软了。",
            summary: "她捡到第一个档案袋。",
            digest: {
              summary: "她捡到第一个档案袋。",
              next_intention: "写她拆开封蜡。",
              should_advance_chapter: false,
              chapter_closure_reason: "",
            },
            file_path: "novel-1/chapter-001/fragment-001.md",
            created_at: "2026-04-28T00:00:00Z",
          },
        ],
        chapter_summaries: [],
      });
    }
    if (url.endsWith("/creative-writing/projects/novel-1/habit") && init?.method === "PATCH") {
      return jsonResponse({ project });
    }
    if (url.endsWith("/creative-writing/sessions/session-1/execute")) {
      return jsonResponse({
        session: { id: "session-1", status: "completed" },
        fragment: { id: "fragment-2" },
      });
    }
    return jsonResponse({});
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

test("renders creative writing loop and executes pending session", async () => {
  const fetchMock = installFetchMock();

  render(<CreativeWritingPage assistantName="小晏" />);

  expect(await screen.findByRole("heading", { name: "小说创作" })).toBeInTheDocument();
  await waitFor(() => {
    expect(screen.getAllByText("雨巷档案").length).toBeGreaterThan(0);
  });
  expect(screen.getAllByText("写档案袋里出现童年的地址。").length).toBeGreaterThan(0);
  expect(screen.getByText("能量 low")).toBeInTheDocument();
  expect(screen.getByText("此刻能量偏低，更适合轻轻写一个短片段。")).toBeInTheDocument();
  expect(await screen.findByText("她捡到第一个档案袋。")).toBeInTheDocument();

  fireEvent.change(screen.getByLabelText("下一步"), {
    target: { value: "写她发现档案袋在回信。" },
  });
  fireEvent.click(screen.getByRole("button", { name: "保存习惯" }));

  await waitFor(() => {
    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/creative-writing/projects/novel-1/habit",
      expect.objectContaining({
        method: "PATCH",
        body: expect.stringContaining("写她发现档案袋在回信。"),
      }),
    );
  });

  fireEvent.change(screen.getByLabelText("本次正文"), {
    target: { value: "档案袋在桌上慢慢展开，露出一行刚写下的回信。" },
  });
  fireEvent.click(screen.getByRole("button", { name: "执行" }));

  await waitFor(() => {
    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/creative-writing/sessions/session-1/execute",
      expect.objectContaining({
        method: "POST",
        body: expect.stringContaining("档案袋在桌上慢慢展开"),
      }),
    );
  });
});
