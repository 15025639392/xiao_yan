import { useState, useEffect, useCallback, useRef } from "react";
import {
  fetchMemorySummary,
  fetchMemoryTimeline,
  searchMemories,
  createMemory,
  deleteMemory,
  batchDeleteMemories,
  updateMemory,
  starMemory,
  type MemoryEntryDisplay,
  type MemorySummary,
  type MemoryKind,
} from "../lib/api";
import { subscribeAppRealtime } from "../lib/realtime";

type MemoryPanelProps = {
  className?: string;
};

// ── 记忆类型中文映射 ──
const KIND_LABELS: Record<string, { label: string; icon: string; color: string; bgColor: string }> = {
  fact: { label: "事实", icon: "📌", color: "#3b82f6", bgColor: "rgba(59, 130, 246, 0.1)" },
  episodic: { label: "经历", icon: "💭", color: "#6366f1", bgColor: "rgba(99, 102, 241, 0.1)" },
  semantic: { label: "知识", icon: "📚", color: "#10b981", bgColor: "rgba(16, 185, 129, 0.1)" },
  emotional: { label: "情绪", icon: "💓", color: "#ef4444", bgColor: "rgba(239, 68, 68, 0.1)" },
  chat_raw: { label: "对话", icon: "💬", color: "#9ca3af", bgColor: "rgba(156, 163, 175, 0.1)" },
};

// ── 强度映射（用于边框颜色）──
const STRENGTH_COLORS: Record<string, string> = {
  faint: "rgba(255, 255, 255, 0.1)",
  weak: "rgba(255, 255, 255, 0.2)",
  normal: "rgba(245, 158, 11, 0.4)",
  vivid: "rgba(59, 130, 246, 0.5)",
  core: "rgba(245, 158, 11, 0.8)",
};

// ── 角色映射 ──
const ROLE_LABELS: Record<string, string> = {
  user: "你",
  assistant: "小晏",
  system: "系统",
};

type ViewMode = "timeline" | "cluster";

// ── 主题聚类配置 ──
const THEME_CLUSTERS: Record<string, { label: string; icon: string; keywords: string[] }> = {
  about_user: {
    label: "关于你",
    icon: "👤",
    keywords: ["喜欢", "爱", "讨厌", "名字", "叫", "我是", "我的工作", "我的职业", "我从事", "我的家乡", "我来自"],
  },
  preferences: {
    label: "偏好习惯",
    icon: "⚙️",
    keywords: ["习惯", "偏好", "通常", "经常", "总是", "从不", "喜欢", "不喜欢"],
  },
  schedule: {
    label: "日程待办",
    icon: "📅",
    keywords: ["明天", "后天", "下周", "记得", "提醒", "会议", "约会", "截止", "交", "完成"],
  },
  knowledge: {
    label: "知识观点",
    icon: "💡",
    keywords: ["认为", "觉得", "观点是", "知识", "知道", "了解", "学习"],
  },
  emotions: {
    label: "情绪感受",
    icon: "🎭",
    keywords: ["开心", "难过", "累", "焦虑", "兴奋", "担心", "感觉", "心情"],
  },
  chat: {
    label: "闲聊对话",
    icon: "💬",
    keywords: [],
  },
};

export function MemoryPanel({ className }: MemoryPanelProps) {
  const [summary, setSummary] = useState<MemorySummary | null>(null);
  const [entries, setEntries] = useState<MemoryEntryDisplay[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<MemoryEntryDisplay[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeFilter, setActiveFilter] = useState<string | null>(null);
  const [showSearchOnly, setShowSearchOnly] = useState(false);
  const [viewMode, setViewMode] = useState<ViewMode>("timeline");

  // ── 操作状态 ──
  const [editingId, setEditingId] = useState<string | null>(null);       // 正在编辑的记忆 ID
  const [editContent, setEditContent] = useState("");                     // 编辑框内容
  const [hoveredId, setHoveredId] = useState<string | null>(null);       // 当前 hover 的记忆 ID
  const [deletingId, setDeletingId] = useState<string | null>(null);     // 正在删除的 ID（loading 状态）
  
  // ── 删除确认弹窗状态 ──
  const [deleteModalOpen, setDeleteModalOpen] = useState(false);
  const [deleteModalTarget, setDeleteModalTarget] = useState<{ id: string; content: string } | null>(null);

  // ── 批量选择状态 ──
  const [isBatchMode, setIsBatchMode] = useState(false);                  // 是否进入批量选择模式
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set()); // 已选中的记忆 ID
  const [batchDeleting, setBatchDeleting] = useState(false);              // 批量删除中

  // ── 手动创建记忆状态 ──
  const [isCreating, setIsCreating] = useState(false);                    // 是否展开创建表单
  const [createContent, setCreateContent] = useState("");                 // 创建输入内容
  const [createKind, setCreateKind] = useState<MemoryKind>("fact");      // 创建类型选择
  const [createSubmitting, setCreateSubmitting] = useState(false);        // 创建提交中
  const createInputRef = useRef<HTMLTextAreaElement>(null);               // 创建输入框 ref

  // 加载记忆摘要和时间线
  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      const [summaryData, timelineData] = await Promise.all([
        fetchMemorySummary(),
        fetchMemoryTimeline(40),
      ]);
      setSummary(summaryData);
      setEntries(timelineData.entries);
    } catch {
      // 静默失败 — 后端可能没启动
    } finally {
      setLoading(false);
    }
  }, []);

  // 搜索记忆
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

  // ── 记忆操作处理函数 ──

  /** 删除记忆 */
  const handleDelete = useCallback(async (memoryId: string) => {
    if (deletingId === memoryId) return; // 防重复点击
    setDeletingId(memoryId);
    try {
      await deleteMemory(memoryId);
      // 从列表中移除
      setEntries((prev) => prev.filter((e) => e.id !== memoryId));
      if (searchResults) {
        setSearchResults((prev) => prev?.filter((e) => e.id !== memoryId) ?? null);
      }
      // 关闭弹窗
      setDeleteModalOpen(false);
      setDeleteModalTarget(null);
    } catch {
      // 静默失败 — 后端可能没启动
    } finally {
      setDeletingId(null);
    }
  }, [deletingId, searchResults]);

  /** 关闭删除确认弹窗 */
  const closeDeleteModal = useCallback(() => {
    if (deletingId) return; // 删除中不允许关闭
    setDeleteModalOpen(false);
    setDeleteModalTarget(null);
  }, [deletingId]);

  /** 标记/取消标记重要 */
  const handleStar = useCallback(async (memoryId: string, currentImportance: number) => {
    const willStar = currentImportance < 8; // 当前不够重要就标星，否则取消
    try {
      await starMemory(memoryId, willStar);
      // 更新本地状态
      const updater = (e: MemoryEntryDisplay): MemoryEntryDisplay =>
        e.id === memoryId ? { ...e, importance: willStar ? 9 : 5 } : e;
      setEntries((prev) => prev.map(updater));
      if (searchResults) {
        setSearchResults((prev) => prev?.map(updater) ?? null);
      }
    } catch {
      // 静默失败
    }
  }, [searchResults]);

  /** 开始编辑 */
  const handleStartEdit = useCallback((entry: MemoryEntryDisplay) => {
    setEditingId(entry.id);
    setEditContent(entry.content);
  }, []);

  /** 取消编辑 */
  const handleCancelEdit = useCallback(() => {
    setEditingId(null);
    setEditContent("");
  }, []);

  /** 保存编辑 */
  const handleSaveEdit = useCallback(async (memoryId: string) => {
    const trimmed = editContent.trim();
    if (!trimmed || trimmed.length < 2) {
      handleCancelEdit();
      return;
    }
    try {
      await updateMemory(memoryId, { content: trimmed });
      // 更新本地状态
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
  }, [editContent, searchResults, handleCancelEdit]);

  // ── 手动创建记忆处理函数 ──

  /** 打开/关闭创建表单 */
  const toggleCreateForm = useCallback(() => {
    setIsCreating((prev) => {
      if (!prev) {
        // 打开时聚焦输入框
        setTimeout(() => createInputRef.current?.focus(), 50);
      } else {
        // 关闭时清空
        setCreateContent("");
        setCreateKind("fact");
      }
      return !prev;
    });
  }, []);

  /** 提交创建记忆 */
  const handleCreateMemory = useCallback(async () => {
    const trimmed = createContent.trim();
    if (!trimmed || trimmed.length < 2 || createSubmitting) return;

    setCreateSubmitting(true);
    try {
      const result = await createMemory({
        kind: createKind,
        content: trimmed,
        role: "user",
      });
      // 新记忆插入到列表头部
      const newEntry: MemoryEntryDisplay = result.entry as unknown as MemoryEntryDisplay;
      setEntries((prev) => [newEntry, ...prev]);
      // 重置表单
      setCreateContent("");
      setCreateSubmitting(false);
      setIsCreating(false);
    } catch {
      setCreateSubmitting(false);
      // 静默失败
    }
  }, [createContent, createKind, createSubmitting]);

  // ── 批量操作处理函数 ──

  /** 切换批量选择模式 */
  const toggleBatchMode = useCallback(() => {
    setIsBatchMode((prev) => {
      if (prev) {
        // 退出时清空选择
        setSelectedIds(new Set());
      }
      return !prev;
    });
  }, []);

  /** 切换单个条目的选中状态 */
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

  /** 全选/取消全选 */
  const toggleSelectAll = useCallback(() => {
    setSelectedIds((prev) => {
      // 使用函数式更新，避免依赖 displayEntries
      const currentEntries = showSearchOnly
        ? (searchResults ?? [])
        : activeFilter
          ? entries.filter((e) => e.kind === activeFilter)
          : entries;
      if (prev.size === currentEntries.length) {
        // 已全选，取消全部
        return new Set();
      }
      // 选中全部
      return new Set(currentEntries.map((e) => e.id));
    });
  }, [showSearchOnly, searchResults, activeFilter, entries]);

  /** 批量删除 */
  const handleBatchDelete = useCallback(async () => {
    if (selectedIds.size === 0 || batchDeleting) return;

    const confirmed = window.confirm(`确定删除选中的 ${selectedIds.size} 条记忆？此操作不可恢复。`);
    if (!confirmed) return;

    setBatchDeleting(true);
    try {
      const result = await batchDeleteMemories(Array.from(selectedIds));
      // 从列表中移除已删除的
      const deletedSet = new Set(selectedIds); // 简化处理：假设都删成功了
      setEntries((prev) => prev.filter((e) => !deletedSet.has(e.id)));
      if (searchResults) {
        setSearchResults((prev) => prev?.filter((e) => !deletedSet.has(e.id)) ?? null);
      }
      setSelectedIds(new Set());
      // 如果全部删完了，退出批量模式
      if (result.deleted > 0 && result.failed === 0) {
        setIsBatchMode(false);
      }
    } catch {
      // 静默失败
    } finally {
      setBatchDeleting(false);
    }
  }, [selectedIds, batchDeleting, searchResults]);

  // 初始化加载 + 定时刷新（30秒）
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

  // 防抖搜索
  useEffect(() => {
    if (!searchQuery) return;
    const timer = setTimeout(() => handleSearch(searchQuery), 300);
    return () => clearTimeout(timer);
  }, [searchQuery, handleSearch]);

  // 过滤后的条目
  const displayEntries = showSearchOnly
    ? (searchResults ?? [])
    : activeFilter
      ? entries.filter((e) => e.kind === activeFilter)
      : entries;

  // 格式化时间（相对）
  function formatTime(isoStr: string | null): string {
    if (!isoStr) return "";
    const d = new Date(isoStr);
    const now = new Date();
    const diffMs = now.getTime() - d.getTime();
    const diffMin = Math.floor(diffMs / 60000);

    if (diffMin < 1) return "刚刚";
    if (diffMin < 60) return `${diffMin}分钟前`;
    const diffHr = Math.floor(diffMin / 60);
    if (diffHr < 24) return `${diffHr}小时前`;
    const diffDay = Math.floor(diffHr / 24);
    if (diffDay < 7) return `${diffDay}天前`;
    return d.toLocaleDateString("zh-CN", { month: "short", day: "numeric" });
  }

  // 获取日期分组标签
  function getDateGroup(isoStr: string | null): string {
    if (!isoStr) return "更早";
    const d = new Date(isoStr);
    const now = new Date();
    const diffMs = now.getTime() - d.getTime();
    const diffDay = Math.floor(diffMs / (1000 * 60 * 60 * 24));

    if (diffDay === 0) return "今天";
    if (diffDay === 1) return "昨天";
    if (diffDay < 7) return "本周";
    if (diffDay < 30) return "本月";
    return "更早";
  }

  // 按日期分组记忆
  function groupEntriesByDate(entries: MemoryEntryDisplay[]): [string, MemoryEntryDisplay[]][] {
    const groups = new Map<string, MemoryEntryDisplay[]>();
    
    entries.forEach((entry) => {
      const group = getDateGroup(entry.created_at);
      if (!groups.has(group)) {
        groups.set(group, []);
      }
      groups.get(group)!.push(entry);
    });

    // 按优先级排序分组
    const groupOrder = ["今天", "昨天", "本周", "本月", "更早"];
    return groupOrder
      .filter((g) => groups.has(g))
      .map((g) => [g, groups.get(g)!] as [string, MemoryEntryDisplay[]]);
  }

  // 判断记忆属于哪个主题聚类
  function getThemeCluster(entry: MemoryEntryDisplay): string {
    const text = (entry.content + " " + entry.keywords.join(" ")).toLowerCase();
    
    // 情绪类型直接归到情绪组
    if (entry.kind === "emotional") return "emotions";
    
    // 按关键词匹配
    for (const [clusterId, config] of Object.entries(THEME_CLUSTERS)) {
      if (clusterId === "chat") continue; // chat 组留到最后兜底
      for (const keyword of config.keywords) {
        if (text.includes(keyword.toLowerCase())) {
          return clusterId;
        }
      }
    }
    
    // 默认归到闲聊组
    return "chat";
  }

  // 按主题聚类记忆
  function groupEntriesByTheme(entries: MemoryEntryDisplay[]): [string, MemoryEntryDisplay[]][] {
    const groups = new Map<string, MemoryEntryDisplay[]>();
    
    entries.forEach((entry) => {
      const cluster = getThemeCluster(entry);
      if (!groups.has(cluster)) {
        groups.set(cluster, []);
      }
      groups.get(cluster)!.push(entry);
    });

    // 按优先级排序：有内容的组在前
    const clusterOrder = ["about_user", "schedule", "preferences", "emotions", "knowledge", "chat"];
    return clusterOrder
      .filter((c) => groups.has(c) && groups.get(c)!.length > 0)
      .map((c) => [c, groups.get(c)!] as [string, MemoryEntryDisplay[]]);
  }

  // 渲染单条记忆条目
  function renderMemoryItem(entry: MemoryEntryDisplay) {
    const kindInfo = KIND_LABELS[entry.kind] || KIND_LABELS.chat_raw;
    const borderColor = STRENGTH_COLORS[entry.strength] || STRENGTH_COLORS.normal;
    const isHovered = hoveredId === entry.id;
    const isEditing = editingId === entry.id;
    const isDeleting = deletingId === entry.id;
    const isStarred = entry.importance >= 8;
    const isSelected = selectedIds.has(entry.id);

    return (
      <div
        key={entry.id}
        className={`memory-item${isHovered ? " memory-item--hover" : ""}${isDeleting ? " memory-item--deleting" : ""}${isSelected ? " memory-item--selected" : ""}`}
        style={{ borderLeftColor: borderColor }}
        title={isBatchMode ? undefined : `强度: ${entry.strength} · 保留: ${Math.round(entry.retention_score)}%`}
        onMouseEnter={() => setHoveredId(entry.id)}
        onMouseLeave={() => setHoveredId(null)}
        onClick={() => isBatchMode && toggleSelection(entry.id)}
      >
        {/* 批量模式：复选框 */}
        {isBatchMode && (
          <div className="memory-item__checkbox">
            <input
              type="checkbox"
              checked={isSelected}
              onChange={() => toggleSelection(entry.id)}
              onClick={(e) => e.stopPropagation()}
            />
          </div>
        )}

        {/* 左侧：类型图标（批量模式下缩小） */}
        <div
          className={`memory-item__icon${isBatchMode ? " memory-item__icon--small" : ""}`}
          style={{
            backgroundColor: kindInfo.bgColor,
            color: kindInfo.color,
          }}
        >
          {kindInfo.icon}
        </div>

        {/* 中间：内容 / 编辑框 */}
        <div className="memory-item__body">
          {isEditing ? (
            /* ── 编辑模式 ── */
            <div className="memory-edit-form">
              <textarea
                className="memory-edit-input"
                value={editContent}
                onChange={(e) => setEditContent(e.target.value)}
                autoFocus
                rows={3}
                onKeyDown={(e) => {
                  if (e.key === "Escape") handleCancelEdit();
                  if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) handleSaveEdit(entry.id);
                }}
              />
              <div className="memory-edit-actions">
                <button
                  className="memory-edit-btn memory-edit-btn--save"
                  onClick={() => handleSaveEdit(entry.id)}
                  disabled={!editContent.trim() || editContent.trim().length < 2}
                >
                  保存 (⌘+↵)
                </button>
                <button
                  className="memory-edit-btn memory-edit-btn--cancel"
                  onClick={handleCancelEdit}
                >取消</button>
              </div>
            </div>
          ) : (
            <>
              {/* 正常展示内容 */}
              <p className="memory-item__content">{entry.content}</p>

              {/* 元信息行 */}
              <div className="memory-item__meta">
                <span className="memory-item__badge" style={{ color: kindInfo.color }}>
                  {kindInfo.label}
                </span>
                {entry.role && (
                  <span className="memory-item__role">{ROLE_LABELS[entry.role] || entry.role}</span>
                )}
                {entry.subject && (
                  <span className="memory-item__subject">@{entry.subject}</span>
                )}
                {entry.keywords.slice(0, 3).map((kw) => (
                  <span key={kw} className="memory-item__keyword">{kw}</span>
                ))}
                {isStarred && (
                  <span className="memory-item__star memory-item__star--active" title="已标为重要">★</span>
                )}
              </div>

            </>
          )}
        </div>

        {/* 右侧：操作按钮 + 时间（常驻显示，批量模式下隐藏） */}
        <div className="memory-item__right">
          {!isBatchMode && !isEditing && (
            <div className="memory-item__actions memory-item__actions--visible">
              {/* 标星/取消标星 */}
              <button
                className={`memory-action-btn ${isStarred ? "memory-action-btn--starred" : ""}`}
                onClick={() => handleStar(entry.id, entry.importance)}
                title={isStarred ? "取消标记重要" : "标记为重要"}
              >
                {isStarred ? "★" : "☆"}
              </button>
              {/* 编辑 */}
              <button
                className="memory-action-btn memory-action-btn--edit"
                onClick={() => handleStartEdit(entry)}
                title="编辑内容"
              >
                ✎
              </button>
              {/* 删除 */}
              <button
                className="memory-action-btn memory-action-btn--delete"
                onClick={() => {
                  setDeleteModalTarget({ id: entry.id, content: entry.content });
                  setDeleteModalOpen(true);
                }}
                title="删除此记忆"
              >
                ✕
              </button>
            </div>
          )}
          <span className="memory-item__time">{formatTime(entry.created_at)}</span>
        </div>
      </div>
    );
  }

  return (
    <section className={`memory-panel ${className ?? ""}`}>
      {/* 头部：类型统计 */}
      {summary && summary.available && Object.keys(summary.by_kind).length > 0 && (
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
                >
                  <span>{info.icon}</span>
                  <span>{count}</span>
                </button>
              );
            })}
          </div>
        </div>
      )}

      {/* 搜索框 + 视图切换 + 新建按钮 */}
      <div className="memory-toolbar">
        <div className="memory-search">
          <svg className="memory-search__icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="11" cy="11" r="8"/>
            <line x1="21" y1="21" x2="16.65" y2="16.65"/>
          </svg>
          <input
            type="text"
            className="memory-search__input"
            placeholder="搜索记忆..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
          {searchQuery && (
            <button
              className="memory-search__clear"
              onClick={() => { setSearchQuery(""); setSearchResults(null); setShowSearchOnly(false); }}
            >✕</button>
          )}
        </div>

        <div className="memory-toolbar__actions">
          {/* 批量模式按钮 */}
          <button
            className={`memory-batch-btn ${isBatchMode ? "memory-batch-btn--active" : ""}`}
            onClick={toggleBatchMode}
            title={isBatchMode ? "退出批量选择" : "批量选择记忆"}
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <rect x="3" y="3" width="7" height="7" rx="1"/>
              <rect x="14" y="3" width="7" height="7" rx="1"/>
              <rect x="3" y="14" width="7" height="7" rx="1"/>
              <rect x="14" y="14" width="7" height="7" rx="1"/>
            </svg>
            <span>{isBatchMode ? "完成" : "批量"}</span>
          </button>

          {/* 新建记忆按钮 */}
          <button
            className={`memory-create-btn ${isCreating ? "memory-create-btn--active" : ""}`}
            onClick={toggleCreateForm}
            title={isCreating ? "取消新建" : "手动添加一条记忆"}
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
              <line x1="12" y1="5" x2="12" y2="19"/>
              <line x1="5" y1="12" x2="19" y2="12"/>
            </svg>
            <span>新建</span>
          </button>

          {/* 视图切换 */}
          <div className="memory-view-toggle">
            <button
              className={`memory-view-btn ${viewMode === "timeline" ? "memory-view-btn--active" : ""}`}
              onClick={() => setViewMode("timeline")}
              title="时间线视图"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <rect x="3" y="4" width="18" height="18" rx="2" ry="2"/>
                <line x1="16" y1="2" x2="16" y2="6"/>
                <line x1="8" y1="2" x2="8" y2="6"/>
                <line x1="3" y1="10" x2="21" y2="10"/>
              </svg>
              <span>时间</span>
            </button>
            <button
              className={`memory-view-btn ${viewMode === "cluster" ? "memory-view-btn--active" : ""}`}
              onClick={() => setViewMode("cluster")}
              title="主题聚类视图"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <polygon points="12 2 2 7 12 12 22 7 12 2"/>
                <polyline points="2 17 12 22 22 17"/>
                <polyline points="2 12 12 17 22 12"/>
              </svg>
              <span>主题</span>
            </button>
          </div>
        </div>
      </div>

      {/* 记忆列表 */}
      <div className="memory-list">
        {/* 手动创建表单 */}
        {isCreating && (
          <div className="memory-create-form">
            <textarea
              ref={createInputRef}
              className="memory-create-input"
              placeholder="写下你想记住的内容..."
              value={createContent}
              onChange={(e) => setCreateContent(e.target.value)}
              rows={3}
              disabled={createSubmitting}
              onKeyDown={(e) => {
                if (e.key === "Escape") toggleCreateForm();
                if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) handleCreateMemory();
              }}
            />
            <div className="memory-create-form__footer">
              <div className="memory-create-kind-selector">
                {([
                  ["fact", "📌 事实"],
                  ["episodic", "💭 经历"],
                  ["semantic", "📚 知识"],
                  ["emotional", "💓 情绪"],
                ] as [MemoryKind, string][]).map(([kind, label]) => (
                  <button
                    key={kind}
                    className={`memory-kind-chip ${createKind === kind ? "memory-kind-chip--active" : ""}`}
                    onClick={() => setCreateKind(kind)}
                  >
                    {label}
                  </button>
                ))}
              </div>
              <div className="memory-create-actions">
                <button
                  className="memory-edit-btn memory-edit-btn--save"
                  onClick={handleCreateMemory}
                  disabled={!createContent.trim() || createContent.trim().length < 2 || createSubmitting}
                >
                  {createSubmitting ? "保存中..." : "保存 (⌘+↵)"}
                </button>
                <button
                  className="memory-edit-btn memory-edit-btn--cancel"
                  onClick={toggleCreateForm}
                  disabled={createSubmitting}
                >取消</button>
              </div>
            </div>
          </div>
        )}

        {loading ? (
          <div className="memory-list__skeleton">
            {[...Array(5)].map((_, i) => (
              <div key={i} className="memory-skeleton-item">
                <div className="memory-skeleton-icon" />
                <div className="memory-skeleton-content">
                  <div className="memory-skeleton-line memory-skeleton-line--long" />
                  <div className="memory-skeleton-line memory-skeleton-line--short" />
                </div>
              </div>
            ))}
          </div>
        ) : displayEntries.length === 0 ? (
          <div className="memory-list__empty">
            <span className="memory-list__empty-icon">🌀</span>
            <p>还没有记忆</p>
            <span className="memory-list__empty-hint">开始对话后会自动记录</span>
          </div>
        ) : viewMode === "timeline" ? (
          // 时间线视图
          groupEntriesByDate(displayEntries).map(([dateGroup, groupEntries]) => (
            <div key={dateGroup} className="memory-group">
              {/* 日期分组标题 */}
              <div className="memory-group__header">
                <span className="memory-group__label">{dateGroup}</span>
                <span className="memory-group__count">{groupEntries.length} 条</span>
              </div>

              {/* 该分组下的记忆条目 */}
              <div className="memory-group__items">
                {groupEntries.map(renderMemoryItem)}
              </div>
            </div>
          ))
        ) : (
          // 主题聚类视图
          groupEntriesByTheme(displayEntries).map(([clusterId, clusterEntries]) => {
            const clusterConfig = THEME_CLUSTERS[clusterId];
            return (
              <div key={clusterId} className="memory-cluster">
                {/* 主题分组标题 */}
                <div className="memory-cluster__header">
                  <span className="memory-cluster__icon">{clusterConfig.icon}</span>
                  <span className="memory-cluster__label">{clusterConfig.label}</span>
                  <span className="memory-cluster__count">{clusterEntries.length} 条</span>
                </div>

                {/* 该主题下的记忆条目 */}
                <div className="memory-cluster__items">
                  {clusterEntries.map(renderMemoryItem)}
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* 底部提示 */}
      {!loading && displayEntries.length > 0 && (
        <div className="memory-footer">
          <span>显示 {displayEntries.length} 条</span>
          {showSearchOnly && searchQuery && (
            <button
              className="memory-footer__clear-filter"
              onClick={() => { setShowSearchOnly(false); setSearchQuery(""); }}
            >清除搜索</button>
          )}
        </div>
      )}

      {/* 批量操作浮动工具栏 */}
      {isBatchMode && (
        <div className="memory-batch-toolbar">
          <div className="memory-batch-toolbar__left">
            <button
              className="memory-batch-toolbar__btn"
              onClick={toggleSelectAll}
              disabled={batchDeleting}
            >
              {selectedIds.size === displayEntries.length ? "取消全选" : "全选"}
            </button>
            <span className="memory-batch-toolbar__count">
              已选 {selectedIds.size} 条
            </span>
          </div>
          <div className="memory-batch-toolbar__right">
            <button
              className="memory-batch-toolbar__btn memory-batch-toolbar__btn--danger"
              onClick={handleBatchDelete}
              disabled={selectedIds.size === 0 || batchDeleting}
            >
              {batchDeleting ? "删除中..." : `删除 (${selectedIds.size})`}
            </button>
            <button
              className="memory-batch-toolbar__btn memory-batch-toolbar__btn--secondary"
              onClick={toggleBatchMode}
              disabled={batchDeleting}
            >
              取消
            </button>
          </div>
        </div>
      )}

      {/* 删除确认弹窗 */}
      {deleteModalOpen && deleteModalTarget && (
        <div className="memory-delete-modal-overlay" onClick={closeDeleteModal}>
          <div className="memory-delete-modal" onClick={(e) => e.stopPropagation()}>
            <div className="memory-delete-modal__header">
              <span className="memory-delete-modal__icon">🗑️</span>
              <h4>确认删除记忆？</h4>
            </div>
            <div className="memory-delete-modal__content">
              <p className="memory-delete-modal__warning">此操作不可恢复。</p>
              <div className="memory-delete-modal__preview">
                <span className="memory-delete-modal__preview-label">记忆内容：</span>
                <p className="memory-delete-modal__preview-text">
                  {deleteModalTarget.content.length > 100
                    ? deleteModalTarget.content.slice(0, 100) + "..."
                    : deleteModalTarget.content}
                </p>
              </div>
            </div>
            <div className="memory-delete-modal__actions">
              <button
                className="memory-delete-modal__btn memory-delete-modal__btn--cancel"
                onClick={closeDeleteModal}
                disabled={deletingId === deleteModalTarget.id}
              >
                取消
              </button>
              <button
                className="memory-delete-modal__btn memory-delete-modal__btn--confirm"
                onClick={() => handleDelete(deleteModalTarget.id)}
                disabled={deletingId === deleteModalTarget.id}
              >
                {deletingId === deleteModalTarget.id ? "删除中..." : "确认删除"}
              </button>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
