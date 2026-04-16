import { useMemo, useState } from "react";
import type { MemoryEntryDisplay } from "../../lib/api";
import { Button, Checkbox, Textarea } from "../ui";
import { KIND_LABELS, STRENGTH_COLORS } from "./memoryConstants";
import { formatRelativeTime, roleLabelFor } from "./memoryUtils";

type MemoryItemProps = {
  entry: MemoryEntryDisplay;
  assistantName: string;
  isBatchMode: boolean;
  isSelected: boolean;
  isEditing: boolean;
  isDeleting: boolean;
  editContent: string;
  onEditContentChange: (value: string) => void;
  onToggleSelection: (memoryId: string) => void;
  onStar: (memoryId: string, currentImportance: number) => void;
  onStartEdit: (entry: MemoryEntryDisplay) => void;
  onCancelEdit: () => void;
  onSaveEdit: (memoryId: string) => void;
  onRequestDelete: (memoryId: string, content: string) => void;
};

export function MemoryItem({
  entry,
  assistantName,
  isBatchMode,
  isSelected,
  isEditing,
  isDeleting,
  editContent,
  onEditContentChange,
  onToggleSelection,
  onStar,
  onStartEdit,
  onCancelEdit,
  onSaveEdit,
  onRequestDelete,
}: MemoryItemProps) {
  const [hovered, setHovered] = useState(false);
  const kindInfo = useMemo(() => KIND_LABELS[entry.kind] || KIND_LABELS.chat_raw, [entry.kind]);
  const borderColor = useMemo(
    () => STRENGTH_COLORS[entry.strength] || STRENGTH_COLORS.normal,
    [entry.strength]
  );
  const isStarred = entry.importance >= 8;
  const roleLabel = roleLabelFor(entry.role, assistantName);

  return (
    <div
      className={`memory-item${hovered ? " memory-item--hover" : ""}${isDeleting ? " memory-item--deleting" : ""}${isSelected ? " memory-item--selected" : ""}`}
      style={{ borderLeftColor: borderColor }}
      title={isBatchMode ? undefined : `强度: ${entry.strength} · 保留: ${Math.round(entry.retention_score)}%`}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      onClick={() => isBatchMode && onToggleSelection(entry.id)}
    >
      {isBatchMode ? (
        <div className="memory-item__checkbox">
          <Checkbox
            checked={isSelected}
            onChange={() => onToggleSelection(entry.id)}
            onClick={(e) => e.stopPropagation()}
          />
        </div>
      ) : null}

      <div
        className={`memory-item__icon${isBatchMode ? " memory-item__icon--small" : ""}`}
        style={{
          backgroundColor: kindInfo.bgColor,
          color: kindInfo.color,
        }}
      >
        {kindInfo.icon}
      </div>

      <div className="memory-item__body">
        {isEditing ? (
          <div className="memory-edit-form">
            <Textarea
              className="memory-edit-input"
              value={editContent}
              onChange={(e) => onEditContentChange(e.target.value)}
              autoFocus
              rows={3}
              onKeyDown={(e) => {
                if (e.key === "Escape") onCancelEdit();
                if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) onSaveEdit(entry.id);
              }}
            />
            <div className="memory-edit-actions">
              <Button
                variant="default"
                className="memory-edit-btn memory-edit-btn--save"
                onClick={() => onSaveEdit(entry.id)}
                disabled={!editContent.trim() || editContent.trim().length < 2}
              >
                保存 (⌘+↵)
              </Button>
              <Button variant="secondary" className="memory-edit-btn memory-edit-btn--cancel" onClick={onCancelEdit}>
                取消
              </Button>
            </div>
          </div>
        ) : (
          <>
            <p className="memory-item__content">{entry.content}</p>

            <div className="memory-item__meta">
              <span className="memory-item__badge" style={{ color: kindInfo.color }}>
                {kindInfo.label}
              </span>
              {roleLabel ? <span className="memory-item__role">{roleLabel}</span> : null}
              {entry.subject ? <span className="memory-item__subject">@{entry.subject}</span> : null}
              {entry.keywords.slice(0, 3).map((kw) => (
                <span key={kw} className="memory-item__keyword">
                  {kw}
                </span>
              ))}
              {isStarred ? (
                <span className="memory-item__star memory-item__star--active" title="已标为重要">
                  ★
                </span>
              ) : null}
            </div>
          </>
        )}
      </div>

      <div className="memory-item__right">
        {!isBatchMode && !isEditing ? (
          <div className="memory-item__actions memory-item__actions--visible">
            <Button
              variant="ghost"
              size="icon"
              className={`memory-action-btn ${isStarred ? "memory-action-btn--starred" : ""}`}
              onClick={() => onStar(entry.id, entry.importance)}
              title={isStarred ? "取消标记重要" : "标记为重要"}
            >
              {isStarred ? "★" : "☆"}
            </Button>
            <Button variant="ghost" size="icon" className="memory-action-btn memory-action-btn--edit" onClick={() => onStartEdit(entry)} title="编辑内容">
              ✎
            </Button>
            <Button
              variant="ghost"
              size="icon"
              className="memory-action-btn memory-action-btn--delete"
              onClick={() => onRequestDelete(entry.id, entry.content)}
              title="删除此记忆"
            >
              ✕
            </Button>
          </div>
        ) : null}
        <span className="memory-item__time">{formatRelativeTime(entry.created_at)}</span>
      </div>
    </div>
  );
}
