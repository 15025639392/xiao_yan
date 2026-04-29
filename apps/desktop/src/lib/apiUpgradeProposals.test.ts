import { afterEach, expect, test, vi } from "vitest";

import {
  approveUpgradeProposal,
  fetchUpgradeProposals,
  markUpgradeProposalImplemented,
  rejectUpgradeProposal,
} from "./apiUpgradeProposals";

afterEach(() => {
  vi.restoreAllMocks();
});

test("uses upgrade proposal endpoints with expected methods", async () => {
  const fetchMock = vi.fn(async () =>
    new Response(JSON.stringify({ ok: true, proposals: [], total: 0, proposal: null }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    }),
  );
  vi.stubGlobal("fetch", fetchMock);

  await fetchUpgradeProposals({ status: "submitted", limit: 20 });
  await approveUpgradeProposal("upg-1");
  await rejectUpgradeProposal("upg-1", "先暂缓");
  await markUpgradeProposalImplemented("upg-1");

  expect(fetchMock).toHaveBeenNthCalledWith(
    1,
    "http://127.0.0.1:8000/upgrade-proposals?status=submitted&limit=20",
  );
  expect(fetchMock).toHaveBeenNthCalledWith(
    2,
    "http://127.0.0.1:8000/upgrade-proposals/upg-1/approve",
    expect.objectContaining({
      method: "POST",
      body: JSON.stringify({ approver: "desktop" }),
    }),
  );
  expect(fetchMock).toHaveBeenNthCalledWith(
    3,
    "http://127.0.0.1:8000/upgrade-proposals/upg-1/reject",
    expect.objectContaining({
      method: "POST",
      body: JSON.stringify({ approver: "desktop", reason: "先暂缓" }),
    }),
  );
  expect(fetchMock).toHaveBeenNthCalledWith(
    4,
    "http://127.0.0.1:8000/upgrade-proposals/upg-1/implement",
    expect.objectContaining({ method: "POST" }),
  );
});
