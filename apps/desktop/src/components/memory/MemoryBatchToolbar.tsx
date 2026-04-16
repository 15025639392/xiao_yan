import { Button } from "../ui";

type MemoryBatchToolbarProps = {
  show: boolean;
  selectedCount: number;
  totalDisplayCount: number;
  batchDeleting: boolean;
  onToggleSelectAll: () => void;
  onBatchDelete: () => void;
  onCancel: () => void;
};

export function MemoryBatchToolbar({
  show,
  selectedCount,
  totalDisplayCount,
  batchDeleting,
  onToggleSelectAll,
  onBatchDelete,
  onCancel,
}: MemoryBatchToolbarProps) {
  if (!show) return null;

  return (
    <div className="memory-batch-toolbar">
      <div className="memory-batch-toolbar__left">
        <Button
          variant="secondary"
          className="memory-batch-toolbar__btn"
          onClick={onToggleSelectAll}
          disabled={batchDeleting}
          type="button"
        >
          {selectedCount === totalDisplayCount ? "取消全选" : "全选"}
        </Button>
        <span className="memory-batch-toolbar__count">已选 {selectedCount} 条</span>
      </div>
      <div className="memory-batch-toolbar__right">
        <Button
          variant="destructive"
          className="memory-batch-toolbar__btn memory-batch-toolbar__btn--danger"
          onClick={onBatchDelete}
          disabled={selectedCount === 0 || batchDeleting}
          type="button"
        >
          {batchDeleting ? "删除中..." : `删除 (${selectedCount})`}
        </Button>
        <Button
          variant="secondary"
          className="memory-batch-toolbar__btn memory-batch-toolbar__btn--secondary"
          onClick={onCancel}
          disabled={batchDeleting}
          type="button"
        >
          取消
        </Button>
      </div>
    </div>
  );
}
