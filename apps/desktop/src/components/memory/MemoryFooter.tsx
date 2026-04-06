type MemoryFooterProps = {
  loading: boolean;
  displayCount: number;
  showSearchOnly: boolean;
  searchQuery: string;
  onClearSearch: () => void;
};

export function MemoryFooter({
  loading,
  displayCount,
  showSearchOnly,
  searchQuery,
  onClearSearch,
}: MemoryFooterProps) {
  if (loading || displayCount === 0) return null;

  return (
    <div className="memory-footer">
      <span>显示 {displayCount} 条</span>
      {showSearchOnly && searchQuery ? (
        <button className="memory-footer__clear-filter" onClick={onClearSearch} type="button">
          清除搜索
        </button>
      ) : null}
    </div>
  );
}

