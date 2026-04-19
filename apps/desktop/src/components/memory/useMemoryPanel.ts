import { useCallback, useEffect, useRef, useState } from "react";
import {
  batchDeleteMemories,
  createMemory,
  deleteMemory,
  fetchMemorySummary,
  fetchMemoryTimeline,
  starMemory,
  updateMemory,
  type MemoryEntryDisplay,
  type MemoryKind,
  type MemoryTimelineQuery,
  type MemorySummary,
  type RelationshipSummary,
} from "../../lib/api";
import { subscribeAppRealtime } from "../../lib/realtime";
import type { ViewMode } from "./memoryConstants";

export function useMemoryPanelState() {
  const [summary, setSummary] = useState<MemorySummary | null>(null);
  const [relationship, setRelationship] = useState<RelationshipSummary | null>(null);
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
      const [summaryData, timelineData] = await Promise.all([
        fetchMemorySummary(),
        fetchMemoryTimeline({ limit: 40 }),
      ]);
      setSummary(summaryData);
      setRelationship(summaryData.relationship);
      setEntries(timelineData.entries);
    } catch {
      // 静默失败 — 后端可能没启动
    } finally {
      setLoading(false);
    }
  }, []);

  const handleSearch = useCallback(async (query: string) => {
    const trimmed = query.trim();
    if (!trimmed) {
      setSearchResults(null);
      setShowSearchOnly(false);
      return;
    }
    try {
      const result = await fetchMemoryTimeline({ limit: 20, q: trimmed });
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
        const updater = (e: MemoryEntryDisplay): MemoryEntryDisplay =>
          e.id === memoryId ? { ...e, content: trimmed } : e;
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
      setRelationship(memoryPayload.relationship ?? memoryPayload.summary.relationship ?? null);
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

  function clearSearch() {
    setSearchQuery("");
    setSearchResults(null);
    setShowSearchOnly(false);
  }

  return {
    summary,
    relationship,
    activeFilter,
    setActiveFilter,
    searchQuery,
    setSearchQuery,
    clearSearch,
    isBatchMode,
    toggleBatchMode,
    isCreating,
    toggleCreateForm,
    viewMode,
    setViewMode,
    createContent,
    setCreateContent,
    createKind,
    setCreateKind,
    createSubmitting,
    handleCreateMemory,
    createInputRef,
    loading,
    displayEntries,
    selectedIds,
    editingId,
    editContent,
    setEditContent,
    deletingId,
    toggleSelection,
    handleStar,
    handleStartEdit,
    handleCancelEdit,
    handleSaveEdit,
    setDeleteModalTarget,
    setDeleteModalOpen,
    deleteModalOpen,
    deleteModalTarget,
    closeDeleteModal,
    handleDelete,
    showSearchOnly,
    batchDeleting,
    toggleSelectAll,
    handleBatchDelete,
  };
}
