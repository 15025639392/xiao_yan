import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, vi } from "vitest";

import { CapabilitiesPage } from "./CapabilitiesPage";

afterEach(() => {
  vi.restoreAllMocks();
});

test("approves pending capability request from card action", async () => {
  let pendingRound = 0;

  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);

    if (url.endsWith("/capabilities/contract")) {
      return new Response(
        JSON.stringify({
          version: "v0",
          descriptors: [
            {
              name: "shell.run",
              default_risk_level: "restricted",
              default_requires_approval: true,
              description: "Execute command in sandbox",
              current_binding: "tools execute endpoint",
            },
          ],
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      );
    }

    if (url.endsWith("/capabilities/queue/status")) {
      return new Response(
        JSON.stringify({
          pending: 1,
          pending_approval: 1,
          in_progress: 0,
          completed: 0,
          dead_letter: 0,
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      );
    }

    if (url.includes("/capabilities/jobs")) {
      return new Response(JSON.stringify({ items: [], next_cursor: null }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }

    if (url.includes("/capabilities/approvals/pending")) {
      pendingRound += 1;
      if (pendingRound === 1) {
        return new Response(
          JSON.stringify({
            items: [
              {
                request: {
                  request_id: "req-1",
                  capability: "shell.run",
                  args: { command: "echo hello" },
                  risk_level: "restricted",
                  requires_approval: true,
                  approval_status: "pending",
                  context: { reason: "run test command" },
                },
                queued_at: "2026-04-08T08:00:00+00:00",
              },
            ],
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        );
      }
      return new Response(JSON.stringify({ items: [] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }

    if (url.includes("/capabilities/approvals/history")) {
      return new Response(JSON.stringify({ items: [] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }

    if (url.includes("/capabilities/approvals/req-1/approve") && init?.method === "POST") {
      return new Response(
        JSON.stringify({
          request_id: "req-1",
          status: "pending",
          approval_status: "approved",
          completed_at: null,
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      );
    }

    throw new Error(`unexpected request: ${url}`);
  });

  vi.stubGlobal("fetch", fetchMock);
  render(<CapabilitiesPage />);

  await waitFor(() => {
    expect(screen.getByRole("heading", { name: "外部能力详情" })).toBeInTheDocument();
  });

  fireEvent.click(screen.getByRole("button", { name: "允许这次" }));

  await waitFor(() => {
    expect(
      fetchMock.mock.calls.some(
        ([url, init]) =>
          String(url).includes("/capabilities/approvals/req-1/approve") &&
          init &&
          typeof init === "object" &&
          (init as RequestInit).method === "POST",
      ),
    ).toBe(true);
  });

  await waitFor(() => {
    expect(screen.getByText("当前没有等待确认的请求")).toBeInTheDocument();
  });
});

test("rejects pending capability request from card action", async () => {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);

    if (url.endsWith("/capabilities/contract")) {
      return new Response(
        JSON.stringify({
          version: "v0",
          descriptors: [],
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      );
    }

    if (url.endsWith("/capabilities/queue/status")) {
      return new Response(
        JSON.stringify({
          pending: 1,
          pending_approval: 1,
          in_progress: 0,
          completed: 0,
          dead_letter: 0,
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      );
    }

    if (url.includes("/capabilities/jobs")) {
      return new Response(JSON.stringify({ items: [], next_cursor: null }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }

    if (url.includes("/capabilities/approvals/pending")) {
      return new Response(
        JSON.stringify({
          items: [
            {
              request: {
                request_id: "req-2",
                capability: "shell.run",
                args: { command: "echo blocked" },
                risk_level: "restricted",
                requires_approval: true,
                approval_status: "pending",
                context: { reason: "reject this command" },
              },
              queued_at: "2026-04-08T08:00:00+00:00",
            },
          ],
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      );
    }

    if (url.includes("/capabilities/approvals/history")) {
      return new Response(JSON.stringify({ items: [] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }

    if (url.includes("/capabilities/approvals/req-2/reject") && init?.method === "POST") {
      return new Response(
        JSON.stringify({
          request_id: "req-2",
          status: "completed",
          approval_status: "rejected",
          completed_at: "2026-04-08T08:00:30+00:00",
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      );
    }

    throw new Error(`unexpected request: ${url}`);
  });

  vi.spyOn(window, "prompt").mockReturnValue("不允许执行该命令");
  vi.stubGlobal("fetch", fetchMock);
  render(<CapabilitiesPage />);

  await waitFor(() => {
    expect(screen.getByRole("heading", { name: "外部能力详情" })).toBeInTheDocument();
  });

  fireEvent.click(screen.getByRole("button", { name: "拒绝" }));

  await waitFor(() => {
    expect(
      fetchMock.mock.calls.some(
        ([url, init]) =>
          String(url).includes("/capabilities/approvals/req-2/reject") &&
          init &&
          typeof init === "object" &&
          (init as RequestInit).method === "POST",
      ),
    ).toBe(true);
  });
});

test("shows human-facing runtime labels instead of internal queue identifiers", async () => {
  const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input);

    if (url.endsWith("/capabilities/contract")) {
      return new Response(JSON.stringify({ version: "v0", descriptors: [] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }

    if (url.endsWith("/capabilities/queue/status")) {
      return new Response(
        JSON.stringify({
          pending: 1,
          pending_approval: 1,
          in_progress: 1,
          completed: 0,
          dead_letter: 2,
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      );
    }

    if (url.includes("/capabilities/jobs")) {
      return new Response(
        JSON.stringify({
          items: [
            {
              request_id: "job-12345678",
              capability: "shell.run",
              status: "in_progress",
              attempt: 2,
              max_attempts: 3,
              approval_status: "pending",
            },
          ],
          next_cursor: null,
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      );
    }

    if (url.includes("/capabilities/approvals/pending")) {
      return new Response(
        JSON.stringify({
          items: [
            {
              request: {
                request_id: "req-3",
                capability: "browser.open",
                args: {},
                risk_level: "restricted",
                requires_approval: true,
                approval_status: "pending",
                context: { reason: "需要打开一个网页" },
              },
              queued_at: "2026-04-08T08:00:00+00:00",
            },
          ],
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      );
    }

    if (url.includes("/capabilities/approvals/history")) {
      return new Response(JSON.stringify({ items: [] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }

    throw new Error(`unexpected request: ${url}`);
  });

  vi.stubGlobal("fetch", fetchMock);
  render(<CapabilitiesPage />);

  await waitFor(() => {
    expect(screen.getByText("异常中断")).toBeInTheDocument();
  });

  expect(screen.getByText("第 2 次尝试，共 3 次机会")).toBeInTheDocument();
  expect(screen.getByText(/进入等待于/)).toBeInTheDocument();
  expect(screen.queryByText(/job-12345678/)).not.toBeInTheDocument();
  expect(screen.queryByText(/req-3/)).not.toBeInTheDocument();
});

test("shows human-facing capability names and softer action labels", async () => {
  const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input);

    if (url.endsWith("/capabilities/contract")) {
      return new Response(
        JSON.stringify({
          version: "v0",
          descriptors: [
            {
              name: "shell.run",
              default_risk_level: "restricted",
              default_requires_approval: true,
              description: "Execute command in sandbox",
              current_binding: "tools execute endpoint",
            },
          ],
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      );
    }

    if (url.endsWith("/capabilities/queue/status")) {
      return new Response(
        JSON.stringify({
          pending: 0,
          pending_approval: 1,
          in_progress: 0,
          completed: 0,
          dead_letter: 0,
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      );
    }

    if (url.includes("/capabilities/jobs")) {
      return new Response(JSON.stringify({ items: [], next_cursor: null }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }

    if (url.includes("/capabilities/approvals/pending")) {
      return new Response(
        JSON.stringify({
          items: [
            {
              request: {
                request_id: "req-9",
                capability: "shell.run",
                args: {},
                risk_level: "restricted",
                requires_approval: true,
                approval_status: "pending",
                context: { reason: "需要执行一次命令" },
              },
              queued_at: "2026-04-08T08:00:00+00:00",
            },
          ],
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      );
    }

    if (url.includes("/capabilities/approvals/history")) {
      return new Response(JSON.stringify({ items: [] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }

    throw new Error(`unexpected request: ${url}`);
  });

  vi.stubGlobal("fetch", fetchMock);
  render(<CapabilitiesPage />);

  await waitFor(() => {
    expect(screen.getAllByText("执行命令").length).toBeGreaterThan(0);
  });

  expect(screen.getByText("接入方式:")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "允许这次" })).toBeInTheDocument();
  expect(screen.queryByText("shell.run")).not.toBeInTheDocument();
});
