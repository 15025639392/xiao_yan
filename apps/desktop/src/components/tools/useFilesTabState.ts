import { useEffect, useState } from "react";
import type { DirectoryEntry, FileReadResult, SearchResult } from "../../lib/api";
import { listDirectory, readFile, searchFiles } from "../../lib/api";

export function useFilesTabState() {
  const [currentPath, setCurrentPath] = useState(".");
  const [entries, setEntries] = useState<DirectoryEntry[] | null>(null);
  const [fileContent, setFileContent] = useState<FileReadResult | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResult, setSearchResult] = useState<SearchResult | null>(null);
  const [loading, setLoading] = useState(false);

  async function loadDir(path: string) {
    setLoading(true);
    try {
      const result = await listDirectory(path);
      setEntries(result.entries);
      setCurrentPath(path);
      setFileContent(null);
    } catch {
      // 静默失败
    }
    setLoading(false);
  }

  async function handleReadFile(relPath: string) {
    setLoading(true);
    try {
      const result = await readFile(relPath);
      setFileContent(result);
    } catch {
      // 静默失败
    }
    setLoading(false);
  }

  async function handleSearch() {
    if (!searchQuery.trim()) return;
    setLoading(true);
    try {
      const result = await searchFiles(searchQuery, currentPath);
      setSearchResult(result);
    } catch {
      // 静默失败
    }
    setLoading(false);
  }

  function navigateUp() {
    const parts = currentPath.replace(/\/$/, "").split("/");
    parts.pop();
    void loadDir(parts.join("/") || ".");
  }

  function handleClickEntry(entry: DirectoryEntry) {
    if (entry.type === "dir") {
      void loadDir(`${currentPath}/${entry.path}`);
    } else {
      void handleReadFile(`${currentPath}/${entry.path}`);
    }
  }

  useEffect(() => {
    void loadDir(".");
  }, []);

  return {
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
  };
}
