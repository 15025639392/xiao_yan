import { useState, useEffect, useCallback } from "react";
import {
  fetchMemorySummary,
  fetchMemoryTimeline,
  searchMemories,
  type MemoryEntryDisplay,
  type MemorySummary,
} from "../lib/api";

type MemoryPanelProps = {
  className?: string;
};

// ── 记忆类型中文映射 ──
const KIND_LABELS: Record<string, { label: string; icon: string; color: string }> = {
  fact: { label: "事实", icon: "📌", color: "var(--primary)" },
  episodic: { label: "经历", icon: "💭", color: "var(--info, #6366f1)" },
  semantic: { label: "知识", icon: "📚", color: "var(--success)" },
  emotional: { label: "情绪印记", icon: "💓", color: "var(--danger)" },
  chat_raw: { label: "对话", icon: "💬", color: "var(--text-tertiary)" },
};

// ── 强度标签映射 ──
const STRENGTH_LABELS: Record<string, { label: string; dotColor: string }> = {
  faint: { label: "模糊", dotColor: "var(--text-muted)" },
  weak: { label: "微弱", dotColor: "#9ca3af" },
  normal: { label: "正常", dotColor: "var(--warning)" },
  vivid: { label: "鲜明", dotColor: "var(--primary)" },
  core: { label: "核心", dotColor: "#f59e0b" },
};

// ── 情绪标签映射 ──
const EMOTION_LABELS: Record<string, { label: string; color: string }> = {
  positive: { label: "正面", color: "var(--success)" },
  negative: { label: "负面", color: "var(--danger)" },
  neutral: { label: "中性", color: "var(--text-secondary)" },
  mixed: { label: "复杂", color: "var(--warning)" },
};

export function MemoryPanel({ className }: MemoryPanelProps) {
  const [summary, setSummary] = useState<MemorySummary | null>(null);
  const [entries, setEntries] = useState<MemoryEntryDisplay[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<MemoryEntryDisplay[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeFilter, setActiveFilter] = useState<string | null>(null);
  const [showSearchOnly, setShowSearchOnly] = useState(false);

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

  // 初始化加载 + 定时刷新（30秒）
  useEffect(() => {
    loadData();
    const id = setInterval(loadData, 30000);
    return () => clearInterval(id);
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

  // 格式化时间
  function formatTime(isoStr: string | null): string {
    if (!isoStr) return "";
    const d = new Date(isoStr);
    const now = new Date();
    const diffMs = now.getTime() - d.getTime();
    const diffMin = Math.floor(diffMs / 60000);

    if (diffMin < 1) return "刚刚";
    if (diffMin < 60) return `${diffMin} 分钟前`;
    const diffHr = Math.floor(diffMin / 60);
    if (diffHr < 24) return `${diffHr} 小时前`;
    return d.toLocaleDateString("zh-CN");
  }

  return (
    <section className={`memory-panel ${className ?? ""}`}>
      {/* 头部：标题 + 统计 */}
      <div className="memory-panel__header">
        <div className="memory-panel__title-group">
          <span className="memory-panel__icon">🧠</span>
          <div>
            <h3 className="memory-panel__title">记忆库</h3>
            <p className="memory-panel__subtitle">
              {summary ? `约 ${summary.total_estimated} 条 · ${summary.strong_memories} 条强记忆` : "加载中..."}
            </p>
          </div>
        </div>

        {/* 类型统计 */}
        {summary && summary.available && Object.keys(summary.by_kind).length > 0 && (
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
        )}
      </div>

      {/* 搜索框 */}
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

      {/* 记忆列表 */}
      <div className="memory-list">
        {loading ? (
          <div className="memory-list__skeleton">
            {[...Array(5)].map((_, i) => (
              <div key={i} className="memory-skeleton-item">
                <div className="memory-skeleton-dot" />
                <div className="memory-skeleton-line memory-skeleton-line--long" />
                <div className="memory-skeleton-line memory-skeleton-line--short" />
              </div>
            ))}
          </div>
        ) : displayEntries.length === 0 ? (
          <div className="memory-list__empty">
            <span className="memory-list__empty-icon">🌀</span>
            <p>还没有记忆</p>
            <span className="memory-list__empty-hint">开始对话后会自动记录</span>
          </div>
        ) : (
          displayEntries.map((entry) => {
            const kindInfo = KIND_LABELS[entry.kind] || KIND_LABELS.chat_raw;
            const strengthInfo = STRENGTH_LABELS[entry.strength] || STRENGTH_LABELS.normal;
            const emotionInfo = EMOTION_LABELS[entry.emotion_tag] || EMOTION_LABELS.neutral;

            return (
              <div key={entry.id} className="memory-entry">
                {/* 左侧：类型图标 */}
                <div
                  className="memory-entry__dot"
                  style={{ backgroundColor: kindInfo.color }}
                  title={kindInfo.label}
                >
                  {kindInfo.icon}
                </div>

                {/* 中间：内容 */}
                <div className="memory-entry__body">
                  <div className="memory-entry__header-row">
                    <span className="memory-entry__kind-badge">{kindInfo.label}</span>
                    {entry.role && (
                      <span className="memory-entry__role">{entry.role === "user" ? "你" : "小晏"}</span>
                    )}
                    <span
                      className="memory-entry__strength"
                      style={{ color: strengthInfo.dotColor }}
                      title={`${strengthInfo.label}强度`}
                    >
                      ● {strengthInfo.label}
                    </span>
                    {entry.importance >= 7 && (
                      <span className="memory-entry__important">★</span>
                    )}
                    <span className="memory-entry__time">{formatTime(entry.created_at)}</span>
                  </div>
                  <p className="memory-entry__content">{entry.content}</p>

                  {/* 底部元信息 */}
                  {(entry.subject || entry.keywords.length > 0) && (
                    <div className="memory-entry__meta">
                      {entry.subject && (
                        <span className="memory-entry__subject-tag">@{entry.subject}</span>
                      )}
                      {entry.keywords.slice(0, 4).map((kw) => (
                        <span key={kw} className="memory-entry__keyword">{kw}</span>
                      ))}
                      <span
                        className="memory-entry__emotion-dot"
                        style={{ backgroundColor: emotionInfo.color }}
                        title={emotionInfo.label}
                      />
                    </div>
                  )}

                  {/* 保留分值 */}
                  <div className="memory-entry__retention-bar">
                    <div
                      className="memory-entry__retention-fill"
                      style={{ width: `${entry.retention_score}%` }}
                    />
                  </div>
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
    </section>
  );
}
