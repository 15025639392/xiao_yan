import { FilesDirectoryList } from "./FilesDirectoryList";
import { FileViewer } from "./FileViewer";
import { FilesNav } from "./FilesNav";
import { FilesSearchBar } from "./FilesSearchBar";
import { FilesSearchResults } from "./FilesSearchResults";
import { useFilesTabState } from "./useFilesTabState";

export function FilesTab() {
  const {
    currentPath,
    entries,
    fileContent,
    searchQuery,
    searchResult,
    loading,
    setSearchQuery,
    setFileContent,
    setSearchResult,
    loadDir,
    handleReadFile,
    handleSearch,
    navigateUp,
    handleClickEntry,
  } = useFilesTabState();

  return (
    <div className="files-tab">
      <FilesNav currentPath={currentPath} onNavigateUp={navigateUp} onRefresh={() => void loadDir(currentPath)} />

      <FilesSearchBar searchQuery={searchQuery} onSearchQueryChange={setSearchQuery} onSearch={handleSearch} />

      {fileContent ? (
        <FileViewer fileContent={fileContent} onClose={() => setFileContent(null)} />
      ) : searchResult ? (
        <FilesSearchResults
          searchQuery={searchQuery}
          searchResult={searchResult}
          onReadFile={(filePath) => void handleReadFile(filePath)}
          onBack={() => setSearchResult(null)}
        />
      ) : (
        <FilesDirectoryList loading={loading} entries={entries} onClickEntry={handleClickEntry} />
      )}
    </div>
  );
}
