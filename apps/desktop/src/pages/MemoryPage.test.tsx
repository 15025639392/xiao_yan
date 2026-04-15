import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import { MemoryPage } from "./MemoryPage";

afterEach(() => {
  vi.restoreAllMocks();
});

function buildMemorySummaryResponse() {
  return {
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
  };
}

test("requests knowledge namespace timeline after switching to structured knowledge mode", async () => {
  const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input);
    if (url.includes("/memory/summary")) {
      return new Response(JSON.stringify(buildMemorySummaryResponse()), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }
    if (url.includes("/memory/timeline")) {
      return new Response(JSON.stringify({ entries: [], total_count: 0, query_summary: null }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }
    throw new Error(`unexpected request: ${url}`);
  });

  vi.stubGlobal("fetch", fetchMock);

  render(<MemoryPage assistantName="小晏" />);

  await waitFor(() => {
    const timelineCalls = fetchMock.mock.calls.filter(([input]) => String(input).includes("/memory/timeline"));
    expect(timelineCalls.length).toBeGreaterThan(0);
  });

  fireEvent.click(screen.getByRole("tab", { name: "结构化知识" }));

  await waitFor(() => {
    const hasKnowledgeScopedCall = fetchMock.mock.calls.some(([input]) => {
      const url = new URL(String(input));
      return (
        url.pathname === "/memory/timeline"
        && url.searchParams.get("namespace") === "knowledge"
        && url.searchParams.get("limit") === "40"
      );
    });
    expect(hasKnowledgeScopedCall).toBe(true);
  });
});

test("keeps knowledge namespace when searching in structured knowledge mode", async () => {
  const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input);
    if (url.includes("/memory/summary")) {
      return new Response(JSON.stringify(buildMemorySummaryResponse()), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }
    if (url.includes("/memory/timeline")) {
      return new Response(JSON.stringify({ entries: [], total_count: 0, query_summary: null }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }
    throw new Error(`unexpected request: ${url}`);
  });

  vi.stubGlobal("fetch", fetchMock);

  render(<MemoryPage assistantName="小晏" />);

  fireEvent.click(screen.getByRole("tab", { name: "结构化知识" }));
  fireEvent.change(screen.getByPlaceholderText("搜索记忆..."), {
    target: { value: "知识抽取" },
  });

  await waitFor(() => {
    const hasKnowledgeSearchCall = fetchMock.mock.calls.some(([input]) => {
      const url = new URL(String(input));
      return (
        url.pathname === "/memory/timeline"
        && url.searchParams.get("namespace") === "knowledge"
        && url.searchParams.get("q") === "知识抽取"
      );
    });
    expect(hasKnowledgeSearchCall).toBe(true);
  });
});

test("loads knowledge review workbench data after switching to review mode", async () => {
  const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input);
    if (url.includes("/memory/summary")) {
      return new Response(JSON.stringify(buildMemorySummaryResponse()), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }
    if (url.includes("/memory/timeline")) {
      return new Response(JSON.stringify({ entries: [], total_count: 0, query_summary: null }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }
    if (url.includes("/knowledge/summary")) {
      return new Response(
        JSON.stringify({
          total_count: 2,
          active_count: 2,
          deleted_count: 0,
          by_review_status: { pending_review: 1, approved: 1, rejected: 0 },
          by_kind: { fact: 2 },
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        },
      );
    }
    if (url.includes("/knowledge/items")) {
      return new Response(
        JSON.stringify({
          items: [
            {
              id: "mem_knowledge_1",
              kind: "fact",
              content: "待审核知识：用户偏好先结论后细节",
              role: "user",
              namespace: "knowledge",
              knowledge_type: "preference",
              knowledge_tags: ["preference"],
              source_ref: "extract://chat",
              version_tag: "v1",
              visibility: "internal",
              governance_source: "auto_extracted",
              review_status: "pending_review",
              reviewed_by: null,
              reviewed_at: null,
              review_note: null,
              status: "active",
              created_at: "2026-04-13T09:00:00+00:00",
              deleted_at: null,
            },
          ],
          total_count: 1,
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        },
      );
    }
    throw new Error(`unexpected request: ${url}`);
  });

  vi.stubGlobal("fetch", fetchMock);

  render(<MemoryPage assistantName="小晏" />);
  fireEvent.click(screen.getByRole("tab", { name: "知识审核" }));

  await waitFor(() => {
    const hasKnowledgeItemsCall = fetchMock.mock.calls.some(([input]) => {
      const url = new URL(String(input));
      return (
        url.pathname === "/knowledge/items"
        && url.searchParams.get("review_status") === "pending_review"
      );
    });
    expect(hasKnowledgeItemsCall).toBe(true);
  });
});
