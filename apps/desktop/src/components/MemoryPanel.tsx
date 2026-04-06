import { useCallback, useEffect, useRef, useState } from "react";
import {
  batchDeleteMemories,
  createMemory,
  deleteMemory,
  fetchMemorySummary,
  fetchMemoryTimeline,
  searchMemories,
  starMemory,
  updateMemory,
  type MemoryEntryDisplay,
  type MemoryKind,
  type MemorySummary,
} from "../lib/api";
import { subscribeAppRealtime } from "../lib/realtime";
import { KIND_LABELS, type ViewMode } from "./memory/memoryConstants";
import { MemoryDeleteModal } from "./memory/MemoryDeleteModal";
import { MemoryItem } from "./memory/MemoryItem";
import { MemoryList } from "./memory/MemoryList";
import { MemoryCreateForm, MemoryToolbar } from "./memory/MemoryToolbar";

type MemoryPanelProps = {
  assistantName?: string;
  className?: string;
};

export function MemoryPanel({ assistantName = "小晏", className }: MemoryPanelProps) {
  const [summary, setSummary] = useState<MemorySummary | null>(null);
  const [entries, setEntries] = useState<MemoryEntryDisplay[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<MemoryEntryDisplay[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeFilter, setActiveFilter] = useState<string | null>(null);
  const [showSearchOnly, setShowSearchOnly] = useState(false);
  const [viewMode, setViewMode] = useState<ViewMode>("timeline");

  const [editingId, setEditingId] = useState<string | null>(null);
  const [editContent, setEditContent] = useState("");
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const [deleteModalOpen, setDeleteModalOpen] = useState(false);
  const [deleteModalTarget, setDeleteModalTarget] = useState<{ id: string; content: string } | null>(null);

  const [isBatchMode, setIsBatchMode] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [batchDeleting, setBatchDeleting] = useState(false);

  const [isCreating, setIsCreating] = useState(false);
  const [createContent, setCreateContent] = useState("");
  const [createKind, setCreateKind] = useState<MemoryKind>("fact");
  const [createSubmitting, setCreateSubmitting] = useState(false);
  const createInputRef = useRef<HTMLTextAreaElement>(null);

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      const [summaryData, timelineData] = await Promise.all([fetchMemorySummary(), fetchMemoryTimeline(40)]);
      setSummary(summaryData);
      setEntries(timelineData.entries);
    } catch {
      // 静默失败 — 后端可能没启动
    } finally {
      setLoading(false);
    }
  }, []);

  const handleSearch = useCallback(async (query: string) => {
    if (!query.trim()) {
      setSearchResults(null);
      setShowSearchOnly(false);
      return;
    }
    try {
      const result = await searchMemories(query, 20);
      setSearchResults(result.entries);
      setShowSearchOnly(true);
    } catch {
      setSearchResults([]);
    }
  }, []);

  const handleDelete = useCallback(
    async (memoryId: string) => {
      if (deletingId === memoryId) return;
      setDeletingId(memoryId);
      try {
        await deleteMemory(memoryId);
        setEntries((prev) => prev.filter((e) => e.id !== memoryId));
        if (searchResults) {
          setSearchResults((prev) => prev?.filter((e) => e.id !== memoryId) ?? null);
        }
        setDeleteModalOpen(false);
        setDeleteModalTarget(null);
      } catch {
        // 静默失败
      } finally {
        setDeletingId(null);
      }
    },
    [deletingId, searchResults]
  );

  const closeDeleteModal = useCallback(() => {
    if (deletingId) return;
    setDeleteModalOpen(false);
    setDeleteModalTarget(null);
  }, [deletingId]);

  const handleStar = useCallback(
    async (memoryId: string, currentImportance: number) => {
      const willStar = currentImportance < 8;
      try {
        await starMemory(memoryId, willStar);
        const updater = (e: MemoryEntryDisplay): MemoryEntryDisplay =>
          e.id === memoryId ? { ...e, importance: willStar ? 9 : 5 } : e;
        setEntries((prev) => prev.map(updater));
        if (searchResults) {
          setSearchResults((prev) => prev?.map(updater) ?? null);
        }
      } catch {
        // 静默失败
      }
    },
    [searchResults]
  );

  const handleStartEdit = useCallback((entry: MemoryEntryDisplay) => {
    setEditingId(entry.id);
    setEditContent(entry.content);
  }, []);

  const handleCancelEdit = useCallback(() => {
    setEditingId(null);
    setEditContent("");
  }, []);

  const handleSaveEdit = useCallback(
    async (memoryId: string) => {
      const trimmed = editContent.trim();
      if (!trimmed || trimmed.length < 2) {
        handleCancelEdit();
        return;
      }
      try {
        await updateMemory(memoryId, { content: trimmed });
        const updater = (e: MemoryEntryDisplay): MemoryEntryDisplay => (e.id === memoryId ? { ...e, content: trimmed } : e);
        setEntries((prev) => prev.map(updater));
        if (searchResults) {
          setSearchResults((prev) => prev?.map(updater) ?? null);
        }
        handleCancelEdit();
      } catch {
        // 静默失败
      }
    },
    [editContent, searchResults, handleCancelEdit]
  );

  const toggleCreateForm = useCallback(() => {
    setIsCreating((prev) => {
      if (!prev) {
        setTimeout(() => createInputRef.current?.focus(), 50);
      } else {
        setCreateContent("");
        setCreateKind("fact");
      }
      return !prev;
    });
  }, []);

  const handleCreateMemory = useCallback(async () => {
    const trimmed = createContent.trim();
    if (!trimmed || trimmed.length < 2 || createSubmitting) return;

    setCreateSubmitting(true);
    try {
      const result = await createMemory({ kind: createKind, content: trimmed, role: "user" });
      const newEntry: MemoryEntryDisplay = result.entry as unknown as MemoryEntryDisplay;
      setEntries((prev) => [newEntry, ...prev]);
      setCreateContent("");
      setCreateSubmitting(false);
      setIsCreating(false);
    } catch {
      setCreateSubmitting(false);
    }
  }, [createContent, createKind, createSubmitting]);

  const toggleBatchMode = useCallback(() => {
    setIsBatchMode((prev) => {
      if (prev) {
        setSelectedIds(new Set());
      }
      return !prev;
    });
  }, []);

  const toggleSelection = useCallback((memoryId: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(memoryId)) {
        next.delete(memoryId);
      } else {
        next.add(memoryId);
      }
      return next;
    });
  }, []);

  const toggleSelectAll = useCallback(() => {
    setSelectedIds((prev) => {
      const currentEntries = showSearchOnly
        ? (searchResults ?? [])
        : activeFilter
          ? entries.filter((e) => e.kind === activeFilter)
          : entries;
      if (prev.size === currentEntries.length) {
        return new Set();
      }
      return new Set(currentEntries.map((e) => e.id));
    });
  }, [showSearchOnly, searchResults, activeFilter, entries]);

  const handleBatchDelete = useCallback(async () => {
    if (selectedIds.size === 0 || batchDeleting) return;

    const confirmed = window.confirm(`确定删除选中的 ${selectedIds.size} 条记忆？此操作不可恢复。`);
    if (!confirmed) return;

    setBatchDeleting(true);
    try {
      const result = await batchDeleteMemories(Array.from(selectedIds));
      const deletedSet = new Set(selectedIds);
      setEntries((prev) => prev.filter((e) => !deletedSet.has(e.id)));
      if (searchResults) {
        setSearchResults((prev) => prev?.filter((e) => !deletedSet.has(e.id)) ?? null);
      }
      setSelectedIds(new Set());
      if (result.deleted > 0 && result.failed === 0) {
        setIsBatchMode(false);
      }
    } catch {
      // 静默失败
    } finally {
      setBatchDeleting(false);
    }
  }, [selectedIds, batchDeleting, searchResults]);

  useEffect(() => {
    loadData();
    const unsubscribe = subscribeAppRealtime((event) => {
      const memoryPayload =
        event.type === "snapshot" ? event.payload.memory : event.type === "memory_updated" ? event.payload : null;
      if (!memoryPayload) {
        return;
      }

      setSummary(memoryPayload.summary);
      setEntries(memoryPayload.timeline);
      setLoading(false);
    });
    return () => unsubscribe();
  }, [loadData]);

  useEffect(() => {
    if (!searchQuery) return;
    const timer = setTimeout(() => handleSearch(searchQuery), 300);
    return () => clearTimeout(timer);
  }, [searchQuery, handleSearch]);

  const displayEntries = showSearchOnly
    ? (searchResults ?? [])
    : activeFilter
      ? entries.filter((e) => e.kind === activeFilter)
      : entries;

  return (
    <section className={`memory-panel ${className ?? ""}`}>
      {summary && summary.available && Object.keys(summary.by_kind).length > 0 ? (
        <div className="memory-panel__header">
          <div className="memory-stats">
            {Object.entries(summary.by_kind).map(([kind, count]) => {
              const info = KIND_LABELS[kind];
              if (!info) return null;
              return (
                <button
                  key={kind}
                  className={`memory-stats__chip ${activeFilter === kind ? "memory-stats__chip--active" : ""}`}
                  onClick={() => setActiveFilter(activeFilter === kind ? null : kind)}
                  title={info.label}
                  type="button"
                >
                  <span>{info.icon}</span>
                  <span>{count}</span>
                </button>
              );
            })}
          </div>
        </div>
      ) : null}

      <MemoryToolbar
        searchQuery={searchQuery}
        onSearchQueryChange={setSearchQuery}
        onClearSearch={() => {
          setSearchQuery("");
          setSearchResults(null);
          setShowSearchOnly(false);
        }}
        isBatchMode={isBatchMode}
        onToggleBatchMode={toggleBatchMode}
        isCreating={isCreating}
        onToggleCreateForm={toggleCreateForm}
        viewMode={viewMode}
        onViewModeChange={setViewMode}
      />

      <MemoryCreateForm
        open={isCreating}
        createContent={createContent}
        onCreateContentChange={setCreateContent}
        createKind={createKind}
        onCreateKindChange={setCreateKind}
        submitting={createSubmitting}
        onSubmit={handleCreateMemory}
        inputRef={createInputRef}
      />

      <div className="memory-list">
        <MemoryList
          loading={loading}
          entries={displayEntries}
          viewMode={viewMode}
          renderItem={(entry) => (
            <MemoryItem
              key={entry.id}
              entry={entry}
              assistantName={assistantName}
              isBatchMode={isBatchMode}
              isSelected={selectedIds.has(entry.id)}
              isEditing={editingId === entry.id}
              isDeleting={deletingId === entry.id}
              editContent={editContent}
              onEditContentChange={setEditContent}
              onToggleSelection={toggleSelection}
              onStar={handleStar}
              onStartEdit={handleStartEdit}
              onCancelEdit={handleCancelEdit}
              onSaveEdit={handleSaveEdit}
              onRequestDelete={(id, content) => {
                setDeleteModalTarget({ id, content });
                setDeleteModalOpen(true);
              }}
            />
          )}
        />
      </div>

      {!loading && displayEntries.length > 0 ? (
        <div className="memory-footer">
          <span>显示 {displayEntries.length} 条</span>
          {showSearchOnly && searchQuery ? (
            <button className="memory-footer__clear-filter" onClick={() => { setShowSearchOnly(false); setSearchQuery(""); }} type="button">
              清除搜索
            </button>
          ) : null}
        </div>
      ) : null}

      {isBatchMode ? (
        <div className="memory-batch-toolbar">
          <div className="memory-batch-toolbar__left">
            <button className="memory-batch-toolbar__btn" onClick={toggleSelectAll} disabled={batchDeleting} type="button">
              {selectedIds.size === displayEntries.length ? "取消全选" : "全选"}
            </button>
            <span className="memory-batch-toolbar__count">已选 {selectedIds.size} 条</span>
          </div>
          <div className="memory-batch-toolbar__right">
            <button
              className="memory-batch-toolbar__btn memory-batch-toolbar__btn--danger"
              onClick={handleBatchDelete}
              disabled={selectedIds.size === 0 || batchDeleting}
              type="button"
            >
              {batchDeleting ? "删除中..." : `删除 (${selectedIds.size})`}
            </button>
            <button
              className="memory-batch-toolbar__btn memory-batch-toolbar__btn--secondary"
              onClick={toggleBatchMode}
              disabled={batchDeleting}
              type="button"
            >
              取消
            </button>
          </div>
        </div>
      ) : null}

      <MemoryDeleteModal
        open={Boolean(deleteModalOpen && deleteModalTarget)}
        contentPreview={
          deleteModalTarget
            ? deleteModalTarget.content.length > 100
              ? deleteModalTarget.content.slice(0, 100) + "..."
              : deleteModalTarget.content
            : ""
        }
        deleting={Boolean(deleteModalTarget && deletingId === deleteModalTarget.id)}
        onCancel={closeDeleteModal}
        onConfirm={() => deleteModalTarget && handleDelete(deleteModalTarget.id)}
      />
    </section>
  );
}

