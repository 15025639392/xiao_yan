import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import { KnowledgeReviewPanel } from "./KnowledgeReviewPanel";

afterEach(() => {
  vi.restoreAllMocks();
});

test("loads next knowledge page with cursor and appends items", async () => {
  const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
    const url = new URL(String(input));

    if (url.pathname === "/knowledge/summary") {
      return new Response(
        JSON.stringify({
          total_count: 3,
          active_count: 3,
          deleted_count: 0,
          by_review_status: { pending_review: 3, approved: 0, rejected: 0 },
          by_kind: { fact: 3 },
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      );
    }

    if (url.pathname === "/knowledge/items") {
      const cursor = url.searchParams.get("cursor");
      if (!cursor) {
        return new Response(
          JSON.stringify({
            items: [
              {
                id: "mem_k_1",
                kind: "fact",
                content: "第一页知识-1",
                role: "user",
                namespace: "knowledge",
                knowledge_type: "preference",
                knowledge_tags: [],
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
              {
                id: "mem_k_2",
                kind: "fact",
                content: "第一页知识-2",
                role: "user",
                namespace: "knowledge",
                knowledge_type: "preference",
                knowledge_tags: [],
                source_ref: "extract://chat",
                version_tag: "v1",
                visibility: "internal",
                governance_source: "auto_extracted",
                review_status: "pending_review",
                reviewed_by: null,
                reviewed_at: null,
                review_note: null,
                status: "active",
                created_at: "2026-04-13T09:01:00+00:00",
                deleted_at: null,
              },
            ],
            total_count: 3,
            next_cursor: "cursor_page_2",
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        );
      }

      if (cursor === "cursor_page_2") {
        return new Response(
          JSON.stringify({
            items: [
              {
                id: "mem_k_3",
                kind: "fact",
                content: "第二页知识-3",
                role: "user",
                namespace: "knowledge",
                knowledge_type: "preference",
                knowledge_tags: [],
                source_ref: "extract://chat",
                version_tag: "v1",
                visibility: "internal",
                governance_source: "auto_extracted",
                review_status: "pending_review",
                reviewed_by: null,
                reviewed_at: null,
                review_note: null,
                status: "active",
                created_at: "2026-04-13T09:02:00+00:00",
                deleted_at: null,
              },
            ],
            total_count: 3,
            next_cursor: null,
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        );
      }
    }

    throw new Error(`unexpected request: ${String(input)}`);
  });

  vi.stubGlobal("fetch", fetchMock);

  const { container } = render(<KnowledgeReviewPanel />);

  await waitFor(() => {
    expect(screen.getByText("第一页知识-1")).toBeInTheDocument();
    expect(screen.getByText("第一页知识-2")).toBeInTheDocument();
  });

  const listElement = container.querySelector(".knowledge-review-panel__list") as HTMLDivElement | null;
  expect(listElement).toBeTruthy();
  if (!listElement) {
    throw new Error("knowledge review list not found");
  }
  Object.defineProperty(listElement, "scrollHeight", { configurable: true, value: 1000 });
  Object.defineProperty(listElement, "clientHeight", { configurable: true, value: 300 });
  Object.defineProperty(listElement, "scrollTop", { configurable: true, value: 680, writable: true });
  fireEvent.scroll(listElement);

  await waitFor(() => {
    expect(screen.getByText("第二页知识-3")).toBeInTheDocument();
  });

  const hasCursorCall = fetchMock.mock.calls.some(([input]) => {
    const url = new URL(String(input));
    return url.pathname === "/knowledge/items" && url.searchParams.get("cursor") === "cursor_page_2";
  });
  expect(hasCursorCall).toBe(true);
});

test("uses reviewed_at sort when review filter switches to approved", async () => {
  const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
    const url = new URL(String(input));

    if (url.pathname === "/knowledge/summary") {
      return new Response(
        JSON.stringify({
          total_count: 1,
          active_count: 1,
          deleted_count: 0,
          by_review_status: { pending_review: 0, approved: 1, rejected: 0 },
          by_kind: { fact: 1 },
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      );
    }

    if (url.pathname === "/knowledge/items") {
      return new Response(
        JSON.stringify({
          items: [
            {
              id: "mem_k_approved_1",
              kind: "fact",
              content: "已通过知识",
              role: "user",
              namespace: "knowledge",
              knowledge_type: "preference",
              knowledge_tags: [],
              source_ref: "manual://review",
              version_tag: "v1",
              visibility: "internal",
              governance_source: "manual",
              review_status: "approved",
              reviewed_by: "owner",
              reviewed_at: "2026-04-13T10:00:00+00:00",
              review_note: "ok",
              status: "active",
              created_at: "2026-04-13T09:00:00+00:00",
              deleted_at: null,
            },
          ],
          total_count: 1,
          next_cursor: null,
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      );
    }

    throw new Error(`unexpected request: ${String(input)}`);
  });

  vi.stubGlobal("fetch", fetchMock);

  render(<KnowledgeReviewPanel />);

  fireEvent.click(screen.getByRole("tab", { name: "已通过" }));

  await waitFor(() => {
    const hasReviewedSortCall = fetchMock.mock.calls.some(([input]) => {
      const url = new URL(String(input));
      return (
        url.pathname === "/knowledge/items"
        && url.searchParams.get("review_status") === "approved"
        && url.searchParams.get("sort_by") === "reviewed_at"
        && url.searchParams.get("sort_order") === "desc"
      );
    });
    expect(hasReviewedSortCall).toBe(true);
  });
});

test("auto loads next page when list scrolls near bottom", async () => {
  const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
    const url = new URL(String(input));

    if (url.pathname === "/knowledge/summary") {
      return new Response(
        JSON.stringify({
          total_count: 3,
          active_count: 3,
          deleted_count: 0,
          by_review_status: { pending_review: 3, approved: 0, rejected: 0 },
          by_kind: { fact: 3 },
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      );
    }

    if (url.pathname === "/knowledge/items") {
      const cursor = url.searchParams.get("cursor");
      if (!cursor) {
        return new Response(
          JSON.stringify({
            items: [
              {
                id: "mem_auto_1",
                kind: "fact",
                content: "自动翻页-首页-1",
                role: "user",
                namespace: "knowledge",
                knowledge_type: "preference",
                knowledge_tags: [],
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
              {
                id: "mem_auto_2",
                kind: "fact",
                content: "自动翻页-首页-2",
                role: "user",
                namespace: "knowledge",
                knowledge_type: "preference",
                knowledge_tags: [],
                source_ref: "extract://chat",
                version_tag: "v1",
                visibility: "internal",
                governance_source: "auto_extracted",
                review_status: "pending_review",
                reviewed_by: null,
                reviewed_at: null,
                review_note: null,
                status: "active",
                created_at: "2026-04-13T09:01:00+00:00",
                deleted_at: null,
              },
            ],
            total_count: 3,
            next_cursor: "cursor_auto_2",
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        );
      }

      if (cursor === "cursor_auto_2") {
        return new Response(
          JSON.stringify({
            items: [
              {
                id: "mem_auto_3",
                kind: "fact",
                content: "自动翻页-第二页-3",
                role: "user",
                namespace: "knowledge",
                knowledge_type: "preference",
                knowledge_tags: [],
                source_ref: "extract://chat",
                version_tag: "v1",
                visibility: "internal",
                governance_source: "auto_extracted",
                review_status: "pending_review",
                reviewed_by: null,
                reviewed_at: null,
                review_note: null,
                status: "active",
                created_at: "2026-04-13T09:02:00+00:00",
                deleted_at: null,
              },
            ],
            total_count: 3,
            next_cursor: null,
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        );
      }
    }

    throw new Error(`unexpected request: ${String(input)}`);
  });

  vi.stubGlobal("fetch", fetchMock);

  const { container } = render(<KnowledgeReviewPanel />);

  await waitFor(() => {
    expect(screen.getByText("自动翻页-首页-1")).toBeInTheDocument();
  });

  const listElement = container.querySelector(".knowledge-review-panel__list") as HTMLDivElement | null;
  expect(listElement).toBeTruthy();
  if (!listElement) {
    throw new Error("knowledge review list not found");
  }

  Object.defineProperty(listElement, "scrollHeight", {
    configurable: true,
    value: 1000,
  });
  Object.defineProperty(listElement, "clientHeight", {
    configurable: true,
    value: 300,
  });
  Object.defineProperty(listElement, "scrollTop", {
    configurable: true,
    value: 670,
    writable: true,
  });

  fireEvent.scroll(listElement);

  await waitFor(() => {
    expect(screen.getByText("自动翻页-第二页-3")).toBeInTheDocument();
  });

  const hasCursorCall = fetchMock.mock.calls.some(([input]) => {
    const url = new URL(String(input));
    return url.pathname === "/knowledge/items" && url.searchParams.get("cursor") === "cursor_auto_2";
  });
  expect(hasCursorCall).toBe(true);
});

test("shows retry load-more button only after auto-load failure", async () => {
  let cursorRequestCount = 0;
  const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
    const url = new URL(String(input));

    if (url.pathname === "/knowledge/summary") {
      return new Response(
        JSON.stringify({
          total_count: 3,
          active_count: 3,
          deleted_count: 0,
          by_review_status: { pending_review: 3, approved: 0, rejected: 0 },
          by_kind: { fact: 3 },
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      );
    }

    if (url.pathname === "/knowledge/items") {
      const cursor = url.searchParams.get("cursor");
      if (!cursor) {
        return new Response(
          JSON.stringify({
            items: [
              {
                id: "mem_retry_1",
                kind: "fact",
                content: "重试场景-首页-1",
                role: "user",
                namespace: "knowledge",
                knowledge_type: "preference",
                knowledge_tags: [],
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
              {
                id: "mem_retry_2",
                kind: "fact",
                content: "重试场景-首页-2",
                role: "user",
                namespace: "knowledge",
                knowledge_type: "preference",
                knowledge_tags: [],
                source_ref: "extract://chat",
                version_tag: "v1",
                visibility: "internal",
                governance_source: "auto_extracted",
                review_status: "pending_review",
                reviewed_by: null,
                reviewed_at: null,
                review_note: null,
                status: "active",
                created_at: "2026-04-13T09:01:00+00:00",
                deleted_at: null,
              },
            ],
            total_count: 3,
            next_cursor: "cursor_retry_2",
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        );
      }

      if (cursor === "cursor_retry_2") {
        cursorRequestCount += 1;
        if (cursorRequestCount === 1) {
          return new Response(JSON.stringify({ detail: "temporary failure" }), {
            status: 500,
            headers: { "Content-Type": "application/json" },
          });
        }

        return new Response(
          JSON.stringify({
            items: [
              {
                id: "mem_retry_3",
                kind: "fact",
                content: "重试场景-第二页-3",
                role: "user",
                namespace: "knowledge",
                knowledge_type: "preference",
                knowledge_tags: [],
                source_ref: "extract://chat",
                version_tag: "v1",
                visibility: "internal",
                governance_source: "auto_extracted",
                review_status: "pending_review",
                reviewed_by: null,
                reviewed_at: null,
                review_note: null,
                status: "active",
                created_at: "2026-04-13T09:02:00+00:00",
                deleted_at: null,
              },
            ],
            total_count: 3,
            next_cursor: null,
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        );
      }
    }

    throw new Error(`unexpected request: ${String(input)}`);
  });

  vi.stubGlobal("fetch", fetchMock);

  const { container } = render(<KnowledgeReviewPanel />);

  await waitFor(() => {
    expect(screen.getByText("重试场景-首页-1")).toBeInTheDocument();
  });

  expect(screen.queryByRole("button", { name: /加载更多/ })).toBeNull();

  const listElement = container.querySelector(".knowledge-review-panel__list") as HTMLDivElement | null;
  expect(listElement).toBeTruthy();
  if (!listElement) {
    throw new Error("knowledge review list not found");
  }
  Object.defineProperty(listElement, "scrollHeight", { configurable: true, value: 1000 });
  Object.defineProperty(listElement, "clientHeight", { configurable: true, value: 300 });
  Object.defineProperty(listElement, "scrollTop", { configurable: true, value: 680, writable: true });
  fireEvent.scroll(listElement);

  await waitFor(() => {
    expect(screen.getByRole("button", { name: /重试加载更多/ })).toBeInTheDocument();
  });

  const retryButton = screen.getByRole("button", { name: /重试加载更多/ });
  expect(retryButton).toBeDisabled();
  expect(retryButton).toHaveTextContent(/后/);

  await waitFor(() => {
    expect(screen.getByRole("button", { name: /重试加载更多/ })).not.toBeDisabled();
  });

  fireEvent.click(screen.getByRole("button", { name: /重试加载更多/ }));

  await waitFor(() => {
    expect(screen.getByText("重试场景-第二页-3")).toBeInTheDocument();
  });
});
