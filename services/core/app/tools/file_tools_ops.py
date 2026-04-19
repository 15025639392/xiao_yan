from __future__ import annotations

import fnmatch
import logging
import os
import re
import time as _time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.tools.file_tools_models import DirectoryEntry, DirectoryListResult, SearchResult

logger = logging.getLogger(__name__)


def list_directory(
    full_path: Path,
    *,
    recursive: bool,
    pattern: str | None,
    max_list_entries: int,
) -> DirectoryListResult:
    if not full_path.exists():
        return DirectoryListResult(path=str(full_path), error="directory not found")
    if not full_path.is_dir():
        return DirectoryListResult(path=str(full_path), error="not a directory")

    entries: list[DirectoryEntry] = []
    file_count = 0
    dir_count = 0
    truncated = False

    try:
        items = list(full_path.glob("**/*")) if recursive else list(full_path.iterdir())
        if pattern:
            items = [item for item in items if fnmatch.fnmatch(item.name, pattern)]
        items = [item for item in items if not item.name.startswith(".") or pattern]

        for item in sorted(items)[:max_list_entries]:
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

            entries.append(
                DirectoryEntry(
                    name=item.name,
                    path=str(item.relative_to(full_path)),
                    type=entry_type,
                    size_bytes=size,
                    modified_at=mod_time,
                )
            )

        if len(items) > max_list_entries:
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
    *,
    query: str,
    full_search_path: Path,
    file_pattern: str,
    max_results: int,
    case_sensitive: bool,
) -> SearchResult:
    start = _time.monotonic()
    matches: list[dict[str, Any]] = []
    total = 0

    try:
        flags = 0 if case_sensitive else re.IGNORECASE
        regex = re.compile(re.escape(query), flags)

        for file_item in full_search_path.rglob(file_pattern):
            if not file_item.is_file():
                continue
            try:
                if file_item.stat().st_size > 5 * 1024 * 1024:
                    continue
            except OSError:
                continue

            try:
                text = file_item.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue

            for lineno, line in enumerate(text.split("\n"), 1):
                if regex.search(line):
                    matches.append(
                        {
                            "file": str(file_item.relative_to(full_search_path)),
                            "line": lineno,
                            "context": line.strip()[:200],
                        }
                    )
                    total += 1
                    if len(matches) >= max_results:
                        break

            if len(matches) >= max_results:
                break
    except Exception as exc:
        logger.exception("FileTools: search failed in %s", full_search_path)
        return SearchResult(query=query, error=str(exc))

    return SearchResult(
        query=query,
        matches=matches,
        total_matches=total,
        search_duration_seconds=_time.monotonic() - start,
    )


def get_file_info(full_path: Path) -> dict[str, Any]:
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
