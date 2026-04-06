type FilesSearchBarProps = {
  searchQuery: string;
  onSearchQueryChange: (value: string) => void;
  onSearch: () => void;
};

export function FilesSearchBar({ searchQuery, onSearchQueryChange, onSearch }: FilesSearchBarProps) {
  return (
    <div className="files-search-bar">
      <input
        type="text"
        value={searchQuery}
        onChange={(event) => onSearchQueryChange(event.target.value)}
        onKeyDown={(event) => event.key === "Enter" && void onSearch()}
        placeholder="搜索文件内容..."
        className="files-search-input"
      />
      <button type="button" className="btn btn--primary btn--sm" onClick={() => void onSearch()} disabled={!searchQuery.trim()}>
        搜索
      </button>
    </div>
  );
}
