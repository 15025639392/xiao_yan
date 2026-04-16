import { Button, Input } from "../ui";

type FilesSearchBarProps = {
  searchQuery: string;
  onSearchQueryChange: (value: string) => void;
  onSearch: () => void;
};

export function FilesSearchBar({ searchQuery, onSearchQueryChange, onSearch }: FilesSearchBarProps) {
  return (
    <div className="files-search-bar">
      <Input
        type="text"
        value={searchQuery}
        onChange={(event) => onSearchQueryChange(event.target.value)}
        onKeyDown={(event) => event.key === "Enter" && void onSearch()}
        placeholder="搜索文件内容..."
        className="files-search-input"
      />
      <Button type="button" variant="default" size="sm" onClick={() => void onSearch()} disabled={!searchQuery.trim()}>
        搜索
      </Button>
    </div>
  );
}
