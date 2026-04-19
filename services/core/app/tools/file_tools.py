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

import logging
from datetime import datetime, timezone
from pathlib import Path

from app.tools.file_tools_mime import guess_mime_type
from app.tools.file_tools_models import (
    DirectoryListResult,
    FileReadResult,
    FileWriteResult,
    SearchResult,
)
from app.tools.file_tools_ops import (
    get_file_info as collect_file_info,
    list_directory as collect_directory_listing,
    search_content as collect_search_results,
)
from app.runtime_ext.runtime_config import FolderAccessLevel

logger = logging.getLogger(__name__)


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
        folder_permissions: dict[str, FolderAccessLevel] | None = None,
        max_read_bytes: int = DEFAULT_MAX_READ_BYTES,
        max_list_entries: int = DEFAULT_MAX_LIST_ENTRIES,
        auto_backup: bool = True,
    ) -> None:
        """
        Args:
            allowed_base_path: 允许访问的基础路径（None 不限制，但会警告）
            folder_permissions: 额外授权目录及其权限级别
            max_read_bytes: 单次读取的最大字节数
            max_list_entries: 目录列表返回的最大条目数
            auto_backup: 写入文件前是否自动备份
        """
        self.allowed_base_path = allowed_base_path
        self.folder_permissions: dict[Path, FolderAccessLevel] = {}
        if folder_permissions:
            for raw_path, access_level in folder_permissions.items():
                resolved = Path(raw_path).expanduser().resolve()
                self.folder_permissions[resolved] = access_level
        self.max_read_bytes = max_read_bytes
        self.max_list_entries = max_list_entries
        self.auto_backup = auto_backup

    def resolve_path(self, relative_or_absolute: str, *, access_mode: str = "read") -> Path:
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

        resolved = p.resolve()

        # 优先允许 base_path 内路径（保持既有行为）
        if self.allowed_base_path is not None:
            base = self.allowed_base_path.resolve()
            try:
                resolved.relative_to(base)
                return resolved
            except ValueError:
                pass

        # 再检查用户授权目录
        for allowed_root, access_level in self.folder_permissions.items():
            try:
                resolved.relative_to(allowed_root)
            except ValueError:
                continue

            if access_mode == "write" and access_level != "full_access":
                raise PermissionError(
                    f"write not allowed in folder: {resolved} (permission: {access_level})"
                )
            return resolved

        # 都不匹配，拒绝访问
        if self.allowed_base_path is not None:
            raise PermissionError(
                f"path outside allowed base and granted folders: {resolved} "
                f"(base: {self.allowed_base_path})"
            )

        raise PermissionError(f"path not allowed: {resolved}")

    def read_file(self, file_path: str, *, max_bytes: int = 0) -> FileReadResult:
        """安全读取文件内容。

        Args:
            file_path: 文件路径（相对或绝对）
            max_bytes: 本次读取的最大字节数（0=使用默认值）
        """
        limit = max_bytes or self.max_read_bytes

        try:
            full_path = self.resolve_path(file_path, access_mode="read")
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
            full_path = self.resolve_path(file_path, access_mode="write")
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
            full_path = self.resolve_path(dir_path, access_mode="read")
        except (PermissionError, ValueError) as exc:
            return DirectoryListResult(path=dir_path, error=str(exc))

        if not full_path.exists():
            return DirectoryListResult(path=str(full_path), error="directory not found")
        if not full_path.is_dir():
            return DirectoryListResult(path=str(full_path), error="not a directory")
        return collect_directory_listing(
            full_path,
            recursive=recursive,
            pattern=pattern,
            max_list_entries=self.max_list_entries,
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
        try:
            full_search_path = self.resolve_path(search_path, access_mode="read")
        except (PermissionError, ValueError):
            return SearchResult(query=query, error="path outside allowed base")
        return collect_search_results(
            query=query,
            full_search_path=full_search_path,
            file_pattern=file_pattern,
            max_results=max_results,
            case_sensitive=case_sensitive,
        )

    def get_file_info(self, file_path: str) -> dict[str, object]:
        """获取文件的详细元信息。"""
        try:
            full_path = self.resolve_path(file_path, access_mode="read")
        except (PermissionError, ValueError) as exc:
            return {"path": file_path, "error": str(exc)}
        return collect_file_info(full_path)

    @staticmethod
    def _guess_mime_type(path: Path) -> str:
        return guess_mime_type(path)
