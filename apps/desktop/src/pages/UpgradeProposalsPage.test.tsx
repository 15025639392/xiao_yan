import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import { UpgradeProposalsPage } from "./UpgradeProposalsPage";

afterEach(() => {
  vi.restoreAllMocks();
});

function jsonResponse(body: unknown) {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

test("renders pending proposal details and approves it", async () => {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    if (url.includes("/upgrade-proposals?")) {
      return jsonResponse({
        total: 1,
        proposals: [
          {
            proposal_id: "upg-1",
            created_at: "2026-04-29T21:08:12+08:00",
            status: "submitted",
            her_voice: "最近状态不太好，这个节奏可能需要调整一下。",
            motivation: "最近状态不太好，inner memory 中多次表达疲惫",
            pain_points: ["多次记录到疲惫状态"],
            observed_data: { tired_inner_count: 3 },
            category: "habit_adjustment",
            target_domain: "general",
            suggested_priority: "low",
          },
        ],
      });
    }
    if (url.endsWith("/upgrade-proposals/upg-1/approve") && init?.method === "POST") {
      return jsonResponse({ ok: true, proposal: null });
    }
    return jsonResponse({ total: 0, proposals: [] });
  });
  vi.stubGlobal("fetch", fetchMock);

  render(<UpgradeProposalsPage />);

  expect(await screen.findByRole("heading", { name: "升级计划" })).toBeInTheDocument();
  expect(screen.getByText("最近状态不太好，这个节奏可能需要调整一下。")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: /通过/ }));

  await waitFor(() => {
    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/upgrade-proposals/upg-1/approve",
      expect.objectContaining({ method: "POST" }),
    );
  });
});
