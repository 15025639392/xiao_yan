from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class FileReadResult:
    """文件读取结果。"""

    path: str
    content: str
    size_bytes: int
    encoding: str = "utf-8"
    line_count: int = 0
    truncated: bool = False
    error: str | None = None
    mime_type: str | None = None

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "path": str(self.path),
            "size_bytes": self.size_bytes,
            "encoding": self.encoding,
            "line_count": self.line_count,
            "truncated": self.truncated,
        }
        if self.error:
            data["error"] = self.error
        if self.mime_type:
            data["mime_type"] = self.mime_type
        return data


@dataclass
class FileWriteResult:
    """文件写入结果。"""

    path: str
    success: bool
    bytes_written: int = 0
    backup_path: str | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "path": str(self.path),
            "success": self.success,
            "bytes_written": self.bytes_written,
        }
        if self.backup_path:
            data["backup_path"] = self.backup_path
        if self.error:
            data["error"] = self.error
        return data


@dataclass
class DirectoryEntry:
    """目录条目。"""

    name: str
    path: str
    type: str  # file / dir / symlink / other
    size_bytes: int = 0
    modified_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "path": str(self.path),
            "type": self.type,
            "size_bytes": self.size_bytes,
            "modified_at": self.modified_at,
        }


@dataclass
class DirectoryListResult:
    """目录列表结果。"""

    path: str
    entries: list[DirectoryEntry] = field(default_factory=list)
    total_files: int = 0
    total_dirs: int = 0
    error: str | None = None
    truncated: bool = False

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "path": str(self.path),
            "entries": [entry.to_dict() for entry in self.entries],
            "total_files": self.total_files,
            "total_dirs": self.total_dirs,
            "truncated": self.truncated,
        }
        if self.error:
            data["error"] = self.error
        return data


@dataclass
class SearchResult:
    """文件搜索结果。"""

    query: str
    matches: list[dict[str, Any]] = field(default_factory=list)
    total_matches: int = 0
    search_duration_seconds: float = 0.0
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "query": self.query,
            "matches": self.matches[:100],
            "total_matches": self.total_matches,
            "search_duration_seconds": round(self.search_duration_seconds, 3),
        }
        if self.error:
            data["error"] = self.error
        return data


__all__ = [
    "FileReadResult",
    "FileWriteResult",
    "DirectoryEntry",
    "DirectoryListResult",
    "SearchResult",
]
