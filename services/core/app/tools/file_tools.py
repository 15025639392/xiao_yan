"""
File Tools — 安全文件操作工具集

提供比裸命令执行更高级、更安全的文件操作接口:
- 文件读取（带大小限制和编码检测）
- 文件写入（带路径限制和备份）
- 目录列表（结构化输出）
- 文件搜索（按模式/内容）
- 统计信息

所有操作都受限于 allowed_base_path，防止越权访问。
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


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
        d: dict[str, Any] = {
            "path": str(self.path),
            "size_bytes": self.size_bytes,
            "encoding": self.encoding,
            "line_count": self.line_count,
            "truncated": self.truncated,
        }
        if self.error:
            d["error"] = self.error
        if self.mime_type:
            d["mime_type"] = self.mime_type
        return d


@dataclass
class FileWriteResult:
    """文件写入结果。"""
    path: str
    success: bool
    bytes_written: int = 0
    backup_path: str | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "path": str(self.path),
            "success": self.success,
            "bytes_written": self.bytes_written,
        }
        if self.backup_path:
            d["backup_path"] = self.backup_path
        if self.error:
            d["error"] = self.error
        return d


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
        d: dict[str, Any] = {
            "path": str(self.path),
            "entries": [e.to_dict() for e in self.entries],
            "total_files": self.total_files,
            "total_dirs": self.total_dirs,
            "truncated": self.truncated,
        }
        if self.error:
            d["error"] = self.error
        return d


@dataclass
class SearchResult:
    """文件搜索结果。"""
    query: str
    matches: list[dict[str, Any]] = field(default_factory=list)
    total_matches: int = 0
    search_duration_seconds: float = 0.0
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "query": self.query,
            "matches": self.matches[:100],  # 最多返回 100 条详情
            "total_matches": self.total_matches,
            "search_duration_seconds": round(self.search_duration_seconds, 3),
        }
        if self.error:
            d["error"] = self.error
        return d


# ── 工具类 ──────────────────────────────────────────────


class FileTools:
    """安全文件操作工具集。

    用法::

        tools = FileTools(
            allowed_base_path=Path("/project/root"),
            max_read_size=1024*1024,  # 1MB
        )

        # 读取文件
        result = tools.read_file("src/app.py")

        # 列出目录
        result = tools.list_directory("services/core/app")

        # 搜索文件
        result = tools.search_content("TODO", "services/", max_results=20)

    安全规则:
    - 所有路径解析为绝对路径后，必须在 allowed_base_path 内
    - 禁止符号链接跟随到 base_path 外部
    - 读取有大小限制，写入自动备份原文件
    - 敏感文件 (.env, .ssh/) 访问时发出警告日志
    """

    DEFAULT_MAX_READ_BYTES = 512 * 1024   # 512 KB
    DEFAULT_MAX_LIST_ENTRIES = 500         # 目录最大条目数
    DEFAULT_MAX_SEARCH_RESULTS = 50
    _SENSITIVE_NAMES = {".env", ".env.local", ".ssh", ".pem", ".key", "id_rsa", "id_dsa"}

    def __init__(
        self,
        *,
        allowed_base_path: Path | None = None,
        max_read_bytes: int = DEFAULT_MAX_READ_BYTES,
        max_list_entries: int = DEFAULT_MAX_LIST_ENTRIES,
        auto_backup: bool = True,
    ) -> None:
        """
        Args:
            allowed_base_path: 允许访问的基础路径（None 不限制，但会警告）
            max_read_bytes: 单次读取的最大字节数
            max_list_entries: 目录列表返回的最大条目数
            auto_backup: 写入文件前是否自动备份
        """
        self.allowed_base_path = allowed_base_path
        self.max_read_bytes = max_read_bytes
        self.max_list_entries = max_list_entries
        self.auto_backup = auto_backup

    def resolve_path(self, relative_or_absolute: str) -> Path:
        """将路径解析为绝对路径并校验安全边界。

        Raises:
            PermissionError: 路径越权
            ValueError: 路径无效
        """
        p = Path(relative_or_absolute)
        if not p.is_absolute():
            # 相对于 base_path 解析
            if self.allowed_base_path:
                p = self.allowed_base_path / p
            else:
                p = Path.cwd() / p
        else:
            p = p.resolve()

        # 安全边界检查
        if self.allowed_base_path is not None:
            try:
                p.resolve().relative_to(self.allowed_base_path.resolve())
            except ValueError:
                raise PermissionError(
                    f"path outside allowed base: {p} (base: {self.allowed_base_path})"
                )

        return p.resolve()

    def read_file(self, file_path: str, *, max_bytes: int = 0) -> FileReadResult:
        """安全读取文件内容。

        Args:
            file_path: 文件路径（相对或绝对）
            max_bytes: 本次读取的最大字节数（0=使用默认值）
        """
        limit = max_bytes or self.max_read_bytes

        try:
            full_path = self.resolve_path(file_path)
        except (PermissionError, ValueError) as exc:
            return FileReadResult(path=file_path, content="", size_bytes=0, error=str(exc))

        # 敏感文件检测
        if full_path.name in self._SENSITIVE_NAMES or any(
            part.startswith(".") and part in {".env", ".ssh", ".git"}
            for part in full_path.parts
        ):
            logger.warning("FileTools: reading potentially sensitive file: %s", full_path)

        if not full_path.exists():
            return FileReadResult(path=str(full_path), content="", size_bytes=0, error="file not found")
        if not full_path.is_file():
            return FileReadResult(path=str(full_path), content="", size_bytes=0, error="not a regular file")

        try:
            raw_size = full_path.stat().st_size
            if raw_size > limit:
                with open(full_path, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read(limit)
                lines = content.count("\n") + 1
                return FileReadResult(
                    path=str(full_path),
                    content=content,
                    size_bytes=len(content.encode("utf-8")),
                    line_count=lines,
                    truncated=True,
                    mime_type=self._guess_mime_type(full_path),
                )
            else:
                with open(full_path, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()
                lines = content.count("\n") + 1
                return FileReadResult(
                    path=str(full_path),
                    content=content,
                    size_bytes=raw_size,
                    line_count=lines,
                    truncated=False,
                    mime_type=self._guess_mime_type(full_path),
                )
        except Exception as exc:
            logger.exception("FileTools: read failed for %s", full_path)
            return FileReadResult(path=str(full_path), content="", size_bytes=0, error=str(exc))

    def write_file(self, file_path: str, content: str, *, create_dirs: bool = True) -> FileWriteResult:
        """安全写入文件。

        Args:
            file_path: 目标路径
            content: 要写入的内容
            create_dirs: 是否自动创建父目录
        """
        try:
            full_path = self.resolve_path(file_path)
        except (PermissionError, ValueError) as exc:
            return FileWriteResult(path=file_path, success=False, error=str(exc))

        backup_path_str: str | None = None

        # 自动备份已有文件
        if self.auto_backup and full_path.exists():
            try:
                backup_path = full_path.with_suffix(f"{full_path.suffix}.bak.{datetime.now().strftime('%Y%m%d%H%M%S')}")
                import shutil
                shutil.copy2(full_path, backup_path)
                backup_path_str = str(backup_path)
            except Exception as exc:
                logger.warning("FileTools: backup failed for %s: %s", full_path, exc)

        try:
            if create_dirs:
                full_path.parent.mkdir(parents=True, exist_ok=True)
            written = full_path.write_text(content, encoding="utf-8")
            return FileWriteResult(
                path=str(full_path),
                success=True,
                bytes_written=written,
                backup_path=backup_path_str,
            )
        except Exception as exc:
            logger.exception("FileTools: write failed for %s", full_path)
            return FileWriteResult(path=str(full_path), success=False, error=str(exc))

    def list_directory(
        self, dir_path: str, *, recursive: bool = False, pattern: str | None = None,
    ) -> DirectoryListResult:
        """列出目录内容（结构化输出）。

        Args:
            dir_path: 目录路径
            recursive: 是否递归列出子目录
            pattern: glob 过滤模式（如 "*.py"）
        """
        try:
            full_path = self.resolve_path(dir_path)
        except (PermissionError, ValueError) as exc:
            return DirectoryListResult(path=dir_path, error=str(exc))

        if not full_path.exists():
            return DirectoryListResult(path=str(full_path), error="directory not found")
        if not full_path.is_dir():
            return DirectoryListResult(path=str(full_path), error="not a directory")

        entries: list[DirectoryEntry] = []
        file_count = 0
        dir_count = 0
        truncated = False

        try:
            glob_pattern = "**/*" if recursive else "*"
            items = list(full_path.glob(glob_pattern)) if recursive else list(full_path.iterdir())

            # 应用过滤
            if pattern:
                import fnmatch
                items = [i for i in items if fnmatch.fnmatch(i.name, pattern)]

            # 排除隐藏文件/目录（除非显式请求）
            items = [i for i in items if not i.name.startswith(".") or pattern]

            for item in sorted(items)[:self.max_list_entries]:
                if item.is_symlink():
                    entry_type = "symlink"
                elif item.is_dir():
                    entry_type = "dir"
                    dir_count += 1
                elif item.is_file():
                    entry_type = "file"
                    file_count += 1
                else:
                    entry_type = "other"

                try:
                    stat = item.stat() if entry_type != "symlink" else item.lstat()
                    size = stat.st_size
                    mod_time = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()
                except (OSError, ValueError):
                    size = 0
                    mod_time = None

                entries.append(DirectoryEntry(
                    name=item.name,
                    path=str(item.relative_to(full_path)),
                    type=entry_type,
                    size_bytes=size,
                    modified_at=mod_time,
                ))

            if len(items) > self.max_list_entries:
                truncated = True

        except Exception as exc:
            logger.exception("FileTools: list failed for %s", full_path)
            return DirectoryListResult(path=str(full_path), error=str(exc))

        return DirectoryListResult(
            path=str(full_path),
            entries=entries,
            total_files=file_count,
            total_dirs=dir_count,
            truncated=truncated,
        )

    def search_content(
        self,
        query: str,
        search_path: str = ".",
        *,
        file_pattern: str = "*.py",
        max_results: int = DEFAULT_MAX_SEARCH_RESULTS,
        case_sensitive: bool = False,
    ) -> SearchResult:
        """在文件中搜索文本内容。

        Args:
            query: 搜索关键词或正则表达式
            search_path: 搜索根目录
            file_pattern: 只搜索匹配的文件名模式
            max_results: 最大返回结果数
            case_sensitive: 是否区分大小写
        """
        import time as _time
        start = _time.monotonic()

        try:
            full_search_path = self.resolve_path(search_path)
        except (PermissionError, ValueError):
            return SearchResult(query=query, error="path outside allowed base")

        matches: list[dict[str, Any]] = []
        total = 0

        try:
            flags = 0 if case_sensitive else re.IGNORECASE
            regex = re.compile(re.escape(query), flags)

            for file_item in full_search_path.rglob(file_pattern):
                if not file_item.is_file():
                    continue
                # 跳过大文件
                try:
                    if file_item.stat().st_size > 5 * 1024 * 1024:  # > 5MB
                        continue
                except OSError:
                    continue

                try:
                    text = file_item.read_text(encoding="utf-8", errors="ignore")
                except Exception:
                    continue

                for lineno, line in enumerate(text.split("\n"), 1):
                    if regex.search(line):
                        rel_path = str(file_item.relative_to(full_search_path))
                        matches.append({
                            "file": rel_path,
                            "line": lineno,
                            "context": line.strip()[:200],
                            })
                        total += 1
                        if len(matches) >= max_results:
                            break

                if len(matches) >= max_results:
                    break

        except Exception as exc:
            logger.exception("FileTools: search failed in %s", full_search_path)
            return SearchResult(query=query, error=str(exc))

        elapsed = _time.monotonic() - start
        return SearchResult(
            query=query,
            matches=matches,
            total_matches=total,
            search_duration_seconds=elapsed,
        )

    def get_file_info(self, file_path: str) -> dict[str, Any]:
        """获取文件的详细元信息。"""
        try:
            full_path = self.resolve_path(file_path)
        except (PermissionError, ValueError) as exc:
            return {"path": file_path, "error": str(exc)}

        if not full_path.exists():
            return {"path": str(full_path), "error": "file not found"}

        try:
            stat = full_path.stat()
            return {
                "path": str(full_path),
                "name": full_path.name,
                "size_bytes": stat.st_size,
                "is_file": full_path.is_file(),
                "is_dir": full_path.is_dir(),
                "is_symlink": full_path.is_symlink(),
                "modified_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
                "created_at": datetime.fromtimestamp(stat.st_ctime, tz=timezone.utc).isoformat(),
                "permissions": oct(stat.st_mode)[-3:],
                "extension": full_path.suffix,
                "readable": os.access(full_path, os.R_OK),
                "writable": os.access(full_path, os.W_OK),
            }
        except Exception as exc:
            return {"path": str(full_path), "error": str(exc)}

    @staticmethod
    def _guess_mime_type(path: Path) -> str:
        """简单猜测 MIME 类型（不依赖 python-magic）。"""
        ext_map = {
            ".py": "text/x-python",
            ".js": "text/javascript",
            ".ts": "text/typescript",
            ".tsx": "text/typescript-jsx",
            ".jsx": "text/javascript-jsx",
            ".json": "application/json",
            ".md": "text/markdown",
            ".html": "text/html",
            ".css": "text/css",
            ".yaml": "text/yaml",
            ".yml": "text/yml",
            ".toml": "text/toml",
            ".xml": "text/xml",
            ".csv": "text/csv",
            ".txt": "text/plain",
            ".log": "text/plain",
            ".sh": "text/x-shellscript",
            ".sql": "text/x-sql",
            ".env": "text/x-env",
            ".lock": "text/x-json",
        }
        return ext_map.get(path.suffix.lower(), "application/octet-stream")


# 导入 re（用于 search_content 方法中的正则匹配）
import re
