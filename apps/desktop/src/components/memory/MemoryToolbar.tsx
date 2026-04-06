import type { RefObject } from "react";
import type { MemoryKind } from "../../lib/api";
import type { ViewMode } from "./memoryConstants";
import { KIND_LABELS } from "./memoryConstants";

type MemoryToolbarProps = {
  searchQuery: string;
  onSearchQueryChange: (value: string) => void;
  onClearSearch: () => void;
  isBatchMode: boolean;
  onToggleBatchMode: () => void;
  isCreating: boolean;
  onToggleCreateForm: () => void;
  viewMode: ViewMode;
  onViewModeChange: (mode: ViewMode) => void;
};

export function MemoryToolbar({
  searchQuery,
  onSearchQueryChange,
  onClearSearch,
  isBatchMode,
  onToggleBatchMode,
  isCreating,
  onToggleCreateForm,
  viewMode,
  onViewModeChange,
}: MemoryToolbarProps) {
  return (
    <div className="memory-toolbar">
      <div className="memory-search">
        <svg className="memory-search__icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <circle cx="11" cy="11" r="8" />
          <line x1="21" y1="21" x2="16.65" y2="16.65" />
        </svg>
        <input
          type="text"
          className="memory-search__input"
          placeholder="搜索记忆..."
          value={searchQuery}
          onChange={(e) => onSearchQueryChange(e.target.value)}
        />
        {searchQuery ? (
          <button className="memory-search__clear" onClick={onClearSearch} type="button">
            ✕
          </button>
        ) : null}
      </div>

      <div className="memory-toolbar__actions">
        <button
          className={`memory-batch-btn ${isBatchMode ? "memory-batch-btn--active" : ""}`}
          onClick={onToggleBatchMode}
          title={isBatchMode ? "退出批量选择" : "批量选择记忆"}
          type="button"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <rect x="3" y="3" width="7" height="7" rx="1" />
            <rect x="14" y="3" width="7" height="7" rx="1" />
            <rect x="3" y="14" width="7" height="7" rx="1" />
            <rect x="14" y="14" width="7" height="7" rx="1" />
          </svg>
          <span>{isBatchMode ? "完成" : "批量"}</span>
        </button>

        <button
          className={`memory-create-btn ${isCreating ? "memory-create-btn--active" : ""}`}
          onClick={onToggleCreateForm}
          title={isCreating ? "取消新建" : "手动添加一条记忆"}
          type="button"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
            <line x1="12" y1="5" x2="12" y2="19" />
            <line x1="5" y1="12" x2="19" y2="12" />
          </svg>
          <span>新建</span>
        </button>

        <div className="memory-view-toggle">
          <button
            className={`memory-view-btn ${viewMode === "timeline" ? "memory-view-btn--active" : ""}`}
            onClick={() => onViewModeChange("timeline")}
            title="时间线视图"
            type="button"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
              <line x1="16" y1="2" x2="16" y2="6" />
              <line x1="8" y1="2" x2="8" y2="6" />
              <line x1="3" y1="10" x2="21" y2="10" />
            </svg>
          </button>
          <button
            className={`memory-view-btn ${viewMode === "cluster" ? "memory-view-btn--active" : ""}`}
            onClick={() => onViewModeChange("cluster")}
            title="主题聚类视图"
            type="button"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M3 3h7v7H3z" />
              <path d="M14 3h7v7h-7z" />
              <path d="M3 14h7v7H3z" />
              <path d="M14 14h7v7h-7z" />
            </svg>
          </button>
        </div>
      </div>
    </div>
  );
}

type MemoryCreateFormProps = {
  open: boolean;
  createContent: string;
  onCreateContentChange: (value: string) => void;
  createKind: MemoryKind;
  onCreateKindChange: (kind: MemoryKind) => void;
  submitting: boolean;
  onSubmit: () => void;
  inputRef: RefObject<HTMLTextAreaElement>;
};

export function MemoryCreateForm({
  open,
  createContent,
  onCreateContentChange,
  createKind,
  onCreateKindChange,
  submitting,
  onSubmit,
  inputRef,
}: MemoryCreateFormProps) {
  if (!open) return null;

  return (
    <div className="memory-create-form">
      <textarea
        ref={inputRef}
        className="memory-create-input"
        placeholder="写下想记住的内容..."
        value={createContent}
        onChange={(e) => onCreateContentChange(e.target.value)}
        disabled={submitting}
        rows={3}
        onKeyDown={(e) => {
          if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
            e.preventDefault();
            onSubmit();
          }
        }}
      />
      <div className="memory-create-form__footer">
        <div className="memory-create-kind-selector">
          {(["fact", "episodic", "semantic", "emotional", "chat_raw"] as MemoryKind[]).map((kind) => (
            <button
              key={kind}
              className={`memory-kind-chip ${createKind === kind ? "memory-kind-chip--active" : ""}`}
              type="button"
              onClick={() => onCreateKindChange(kind)}
            >
              {KIND_LABELS[kind]?.label ?? kind}
            </button>
          ))}
        </div>
        <div className="memory-create-actions">
          <button
            className="memory-create-btn-submit"
            type="button"
            onClick={onSubmit}
            disabled={!createContent.trim() || createContent.trim().length < 2 || submitting}
          >
            {submitting ? "保存中..." : "保存 (⌘+↵)"}
          </button>
        </div>
      </div>
    </div>
  );
}
