import type { SearchResult } from "../../lib/api";

type FilesSearchResultsProps = {
  searchQuery: string;
  searchResult: SearchResult;
  onReadFile: (filePath: string) => void;
  onBack: () => void;
};

export function FilesSearchResults({ searchQuery, searchResult, onReadFile, onBack }: FilesSearchResultsProps) {
  return (
    <div className="search-results">
      <h4>
        搜索 "{searchQuery}" — {searchResult.total_matches} 条匹配 ({searchResult.search_duration_seconds}s)
      </h4>
      {searchResult.matches.length > 0 ? (
        <table className="search-results-table">
          <thead>
            <tr>
              <th>文件</th>
              <th>行号</th>
              <th>内容</th>
            </tr>
          </thead>
          <tbody>
            {searchResult.matches.map((match, index) => (
              <tr key={index}>
                <td>
                  <button type="button" className="search-file-link" onClick={() => onReadFile(match.file)}>
                    {match.file}
                  </button>
                </td>
                <td>{match.line}</td>
                <td className="search-context">
                  <code>{match.context}</code>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <p style={{ color: "var(--text-tertiary)" }}>未找到匹配结果</p>
      )}
      <button type="button" className="btn btn--sm" onClick={onBack}>
        返回目录
      </button>
    </div>
  );
}
