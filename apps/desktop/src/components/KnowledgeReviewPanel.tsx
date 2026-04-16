import { type UIEvent, useCallback, useEffect, useMemo, useState } from "react";

import {
  fetchKnowledgeItems,
  fetchKnowledgeSummary,
  reviewKnowledgeItem,
  reviewKnowledgeItemsBatch,
  type KnowledgeItem,
  type KnowledgeReviewStatus,
  type KnowledgeSummaryResponse,
} from "../lib/api";
import { Button, Checkbox, Input } from "./ui";

type KnowledgeReviewPanelProps = {
  className?: string;
};

const REVIEW_STATUS_LABELS: Record<KnowledgeReviewStatus, string> = {
  pending_review: "待审核",
  approved: "已通过",
  rejected: "已驳回",
};
const KNOWLEDGE_PAGE_SIZE = 40;
const LOAD_MORE_SCROLL_THRESHOLD_PX = 64;
const LOAD_MORE_RETRY_BASE_DELAY_SECONDS = 1;
const LOAD_MORE_RETRY_MAX_DELAY_SECONDS = 16;

function mergeKnowledgeItems(previous: KnowledgeItem[], incoming: KnowledgeItem[]): KnowledgeItem[] {
  if (incoming.length === 0) {
    return previous;
  }
  const seen = new Set(previous.map((item) => item.id));
  const merged = [...previous];
  for (const item of incoming) {
    if (seen.has(item.id)) {
      continue;
    }
    seen.add(item.id);
    merged.push(item);
  }
  return merged;
}

export function KnowledgeReviewPanel({ className }: KnowledgeReviewPanelProps) {
  const [summary, setSummary] = useState<KnowledgeSummaryResponse | null>(null);
  const [items, setItems] = useState<KnowledgeItem[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [loadMoreFailed, setLoadMoreFailed] = useState(false);
  const [loadMoreFailureCount, setLoadMoreFailureCount] = useState(0);
  const [retryLockedUntilMs, setRetryLockedUntilMs] = useState<number | null>(null);
  const [retryNowMs, setRetryNowMs] = useState(() => Date.now());
  const [reviewingId, setReviewingId] = useState<string | null>(null);
  const [batchReviewing, setBatchReviewing] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [reviewFilter, setReviewFilter] = useState<KnowledgeReviewStatus | "all">("pending_review");
  const [searchQuery, setSearchQuery] = useState("");
  const [error, setError] = useState("");

  const buildKnowledgeListQuery = useCallback(
    (cursor?: string) => {
      const useReviewedAtSort = reviewFilter === "approved" || reviewFilter === "rejected";
      return {
        limit: KNOWLEDGE_PAGE_SIZE,
        status: "active" as const,
        review_status: reviewFilter === "all" ? undefined : reviewFilter,
        q: searchQuery.trim() || undefined,
        sort_by: useReviewedAtSort ? ("reviewed_at" as const) : ("created_at" as const),
        sort_order: "desc" as const,
        cursor,
      };
    },
    [reviewFilter, searchQuery],
  );

  const loadData = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [summaryData, itemsData] = await Promise.all([
        fetchKnowledgeSummary(),
        fetchKnowledgeItems(buildKnowledgeListQuery()),
      ]);
      setSummary(summaryData);
      setItems(itemsData.items);
      setTotalCount(itemsData.total_count);
      setNextCursor(itemsData.next_cursor ?? null);
      setLoadMoreFailed(false);
      setLoadMoreFailureCount(0);
      setRetryLockedUntilMs(null);
      setRetryNowMs(Date.now());
    } catch {
      setError("加载知识审核数据失败，请确认服务端已启动。");
      setItems([]);
      setTotalCount(0);
      setNextCursor(null);
      setLoadMoreFailed(false);
      setLoadMoreFailureCount(0);
      setRetryLockedUntilMs(null);
      setRetryNowMs(Date.now());
    } finally {
      setLoading(false);
    }
  }, [buildKnowledgeListQuery]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void loadData();
    }, 220);
    return () => window.clearTimeout(timer);
  }, [loadData]);

  useEffect(() => {
    setSelectedIds((prev) => {
      if (prev.size === 0) {
        return prev;
      }
      const visible = new Set(items.map((item) => item.id));
      const next = new Set(Array.from(prev).filter((id) => visible.has(id)));
      return next.size === prev.size ? prev : next;
    });
  }, [items]);

  useEffect(() => {
    if (retryLockedUntilMs == null) {
      return;
    }

    const tick = () => {
      const currentMs = Date.now();
      setRetryNowMs(currentMs);
      if (currentMs >= retryLockedUntilMs) {
        setRetryLockedUntilMs(null);
      }
    };

    tick();
    const countdownTimer = window.setInterval(tick, 250);
    const unlockDelayMs = Math.max(0, retryLockedUntilMs - Date.now());
    const unlockTimer = window.setTimeout(() => {
      setRetryNowMs(Date.now());
      setRetryLockedUntilMs(null);
    }, unlockDelayMs);

    return () => {
      window.clearInterval(countdownTimer);
      window.clearTimeout(unlockTimer);
    };
  }, [retryLockedUntilMs]);

  const retryRemainingSeconds = useMemo(() => {
    if (retryLockedUntilMs == null) {
      return 0;
    }
    return Math.max(0, Math.ceil((retryLockedUntilMs - retryNowMs) / 1000));
  }, [retryLockedUntilMs, retryNowMs]);
  const retryLocked = retryRemainingSeconds > 0;

  const handleLoadMore = useCallback(async () => {
    if (!nextCursor || loadingMore || retryLocked) {
      return;
    }
    setLoadingMore(true);
    setError("");
    try {
      const itemsData = await fetchKnowledgeItems(buildKnowledgeListQuery(nextCursor));
      setItems((prev) => mergeKnowledgeItems(prev, itemsData.items));
      setTotalCount(itemsData.total_count);
      setNextCursor(itemsData.next_cursor ?? null);
      setLoadMoreFailed(false);
      setLoadMoreFailureCount(0);
      setRetryLockedUntilMs(null);
      setRetryNowMs(Date.now());
    } catch {
      setError("加载更多失败，请稍后重试。");
      setLoadMoreFailed(true);
      const nextFailureCount = loadMoreFailureCount + 1;
      const retryDelaySeconds = Math.min(
        LOAD_MORE_RETRY_MAX_DELAY_SECONDS,
        LOAD_MORE_RETRY_BASE_DELAY_SECONDS * (2 ** Math.max(0, nextFailureCount - 1)),
      );
      setLoadMoreFailureCount(nextFailureCount);
      setRetryNowMs(Date.now());
      setRetryLockedUntilMs(Date.now() + (retryDelaySeconds * 1000));
    } finally {
      setLoadingMore(false);
    }
  }, [buildKnowledgeListQuery, loadMoreFailureCount, loadingMore, nextCursor, retryLocked]);

  const handleListScroll = useCallback(
    (event: UIEvent<HTMLDivElement>) => {
      if (loading || loadingMore || !nextCursor || loadMoreFailed) {
        return;
      }
      const element = event.currentTarget;
      const remainingHeight = element.scrollHeight - element.scrollTop - element.clientHeight;
      if (remainingHeight <= LOAD_MORE_SCROLL_THRESHOLD_PX) {
        void handleLoadMore();
      }
    },
    [handleLoadMore, loadMoreFailed, loading, loadingMore, nextCursor],
  );

  const resolveReviewNote = useCallback((decision: "approve" | "reject" | "pend"): string | null | undefined => {
    if (decision !== "reject") {
      return undefined;
    }
    const input = window.prompt("驳回原因（必填）", "");
    if (input == null) {
      return null;
    }
    const trimmed = input.trim();
    if (!trimmed) {
      window.alert("驳回时必须填写原因。");
      return null;
    }
    return trimmed;
  }, []);

  const handleReview = useCallback(
    async (knowledgeId: string, decision: "approve" | "reject" | "pend") => {
      if (reviewingId === knowledgeId) {
        return;
      }
      const reviewNote = resolveReviewNote(decision);
      if (decision === "reject" && !reviewNote) {
        return;
      }
      setReviewingId(knowledgeId);
      setError("");
      try {
        await reviewKnowledgeItem(knowledgeId, {
          decision,
          reviewer: "knowledge-workbench",
          review_note: reviewNote,
        });
        await loadData();
      } catch {
        setError("审核提交失败，请稍后重试。");
      } finally {
        setReviewingId(null);
      }
    },
    [loadData, resolveReviewNote, reviewingId],
  );

  const toggleSelection = useCallback((knowledgeId: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(knowledgeId)) {
        next.delete(knowledgeId);
      } else {
        next.add(knowledgeId);
      }
      return next;
    });
  }, []);

  const toggleSelectAll = useCallback(() => {
    setSelectedIds((prev) => {
      if (items.length === 0) {
        return new Set();
      }
      if (prev.size === items.length) {
        return new Set();
      }
      return new Set(items.map((item) => item.id));
    });
  }, [items]);

  const handleBatchReview = useCallback(
    async (decision: "approve" | "reject" | "pend") => {
      if (selectedIds.size === 0 || batchReviewing) {
        return;
      }
      const confirmed = window.confirm(`确认对 ${selectedIds.size} 条知识执行批量操作吗？`);
      if (!confirmed) {
        return;
      }
      const reviewNote = resolveReviewNote(decision);
      if (decision === "reject" && !reviewNote) {
        return;
      }

      setBatchReviewing(true);
      setError("");
      try {
        const result = await reviewKnowledgeItemsBatch({
          knowledge_ids: Array.from(selectedIds),
          decision,
          reviewer: "knowledge-workbench",
          review_note: reviewNote,
        });
        if (result.failed > 0) {
          setError(`批量审核部分失败：${result.failed}/${selectedIds.size}`);
        }
        setSelectedIds(new Set());
        await loadData();
      } catch {
        setError("批量审核失败，请稍后重试。");
      } finally {
        setBatchReviewing(false);
      }
    },
    [batchReviewing, loadData, resolveReviewNote, selectedIds],
  );

  const stats = useMemo(() => {
    const empty = { pending_review: 0, approved: 0, rejected: 0 };
    if (!summary) {
      return empty;
    }
    return {
      pending_review: summary.by_review_status.pending_review ?? 0,
      approved: summary.by_review_status.approved ?? 0,
      rejected: summary.by_review_status.rejected ?? 0,
    };
  }, [summary]);

  return (
    <section className={`knowledge-review-panel memory-panel ${className ?? ""}`}>
      <header className="knowledge-review-panel__header">
        <h3 className="knowledge-review-panel__title">知识审核工作台</h3>
        <p className="knowledge-review-panel__subtitle">治理自动抽取知识，控制发布质量与可追溯性</p>
      </header>

      <div className="knowledge-review-panel__stats">
        <div className="knowledge-review-panel__stat">
          <span>待审核</span>
          <strong>{stats.pending_review}</strong>
        </div>
        <div className="knowledge-review-panel__stat">
          <span>已通过</span>
          <strong>{stats.approved}</strong>
        </div>
        <div className="knowledge-review-panel__stat">
          <span>已驳回</span>
          <strong>{stats.rejected}</strong>
        </div>
      </div>

      <div className="knowledge-review-panel__toolbar">
        <Input
          className="knowledge-review-panel__search"
          value={searchQuery}
          onChange={(event) => setSearchQuery(event.target.value)}
          placeholder="搜索知识内容或关键词..."
        />
        <div className="knowledge-review-panel__filters" role="tablist" aria-label="审核状态筛选">
          {(["pending_review", "approved", "rejected", "all"] as const).map((status) => (
            <Button
              key={status}
              type="button"
              role="tab"
              aria-selected={reviewFilter === status}
              variant="ghost"
              className={`knowledge-review-panel__filter-btn ${reviewFilter === status ? "knowledge-review-panel__filter-btn--active" : ""}`}
              onClick={() => setReviewFilter(status)}
            >
              {status === "all" ? "全部" : REVIEW_STATUS_LABELS[status]}
            </Button>
          ))}
        </div>
      </div>

      {error ? <div className="knowledge-review-panel__error">{error}</div> : null}

      <div className="knowledge-review-panel__batch">
        <label className="knowledge-review-panel__batch-select">
          <Checkbox
            checked={items.length > 0 && selectedIds.size === items.length}
            onChange={toggleSelectAll}
          />
          <span>全选当前结果</span>
        </label>
        <span className="knowledge-review-panel__batch-count">已选 {selectedIds.size} 条</span>
        <div className="knowledge-review-panel__batch-actions">
          <Button
            type="button"
            disabled={selectedIds.size === 0 || batchReviewing}
            variant="default"
            className="knowledge-review-panel__action-btn knowledge-review-panel__action-btn--approve"
            onClick={() => void handleBatchReview("approve")}
          >
            批量通过
          </Button>
          <Button
            type="button"
            disabled={selectedIds.size === 0 || batchReviewing}
            variant="destructive"
            className="knowledge-review-panel__action-btn knowledge-review-panel__action-btn--reject"
            onClick={() => void handleBatchReview("reject")}
          >
            批量驳回
          </Button>
          <Button
            type="button"
            disabled={selectedIds.size === 0 || batchReviewing}
            variant="secondary"
            className="knowledge-review-panel__action-btn"
            onClick={() => void handleBatchReview("pend")}
          >
            批量置待审
          </Button>
        </div>
      </div>

      <div className="knowledge-review-panel__list" onScroll={handleListScroll}>
        {loading ? <div className="knowledge-review-panel__empty">加载中...</div> : null}
        {!loading && items.length === 0 ? (
          <div className="knowledge-review-panel__empty">当前筛选下没有知识条目</div>
        ) : null}

        {!loading && items.map((item) => (
          <article key={item.id} className="knowledge-review-panel__item">
            <label className="knowledge-review-panel__item-check">
              <Checkbox
                checked={selectedIds.has(item.id)}
                onChange={() => toggleSelection(item.id)}
              />
            </label>
            <div className="knowledge-review-panel__item-main">
              <div className="knowledge-review-panel__item-meta">
                <span className="knowledge-review-panel__pill">{item.kind}</span>
                <span className="knowledge-review-panel__pill">{REVIEW_STATUS_LABELS[item.review_status]}</span>
                <span className="knowledge-review-panel__pill">{item.governance_source}</span>
                {item.knowledge_type ? <span className="knowledge-review-panel__pill">{item.knowledge_type}</span> : null}
              </div>
              <p className="knowledge-review-panel__item-content">{item.content}</p>
              <div className="knowledge-review-panel__item-submeta">
                <span>来源：{item.source_ref ?? "unknown"}</span>
                <span>创建：{item.created_at ?? "-"}</span>
                <span>审核人：{item.reviewed_by ?? "-"}</span>
              </div>
            </div>
            <div className="knowledge-review-panel__item-actions">
              <Button
                type="button"
                disabled={reviewingId === item.id}
                variant="default"
                className="knowledge-review-panel__action-btn knowledge-review-panel__action-btn--approve"
                onClick={() => void handleReview(item.id, "approve")}
              >
                通过
              </Button>
              <Button
                type="button"
                disabled={reviewingId === item.id}
                variant="destructive"
                className="knowledge-review-panel__action-btn knowledge-review-panel__action-btn--reject"
                onClick={() => void handleReview(item.id, "reject")}
              >
                驳回
              </Button>
              <Button
                type="button"
                disabled={reviewingId === item.id}
                variant="secondary"
                className="knowledge-review-panel__action-btn"
                onClick={() => void handleReview(item.id, "pend")}
              >
                置待审
              </Button>
            </div>
          </article>
        ))}

        {!loading && items.length > 0 && nextCursor && loadMoreFailed ? (
          <Button
            type="button"
            variant="secondary"
            className="knowledge-review-panel__load-more"
            disabled={loadingMore || retryLocked}
            onClick={() => void handleLoadMore()}
          >
            {loadingMore
              ? "重试中..."
              : retryLocked
                ? `重试加载更多（${retryRemainingSeconds}s后）`
                : `重试加载更多（${items.length}/${totalCount}）`}
          </Button>
        ) : null}
      </div>
    </section>
  );
}
