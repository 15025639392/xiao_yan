"""
自我编程历史记录存储（Facade）。

拆分说明：
- 数据模型：app.self_programming.history_models
- 统计逻辑：app.self_programming.history_stats
- 本模块保留后端实现与 SelfProgrammingHistory 管理器
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from app.self_programming.history_models import HistoryEntry, HistoryEntryStatus
from app.self_programming.history_stats import build_history_statistics
from app.utils.file_utils import read_json_file, write_json_file, write_text_file

logger = logging.getLogger(__name__)


class MemoryBackend:
    """内存后端。"""

    def __init__(self) -> None:
        self._entries: list[dict] = []

    def save(self, entry_dict: dict) -> None:
        self._entries.append(entry_dict)

    def load_all(self) -> list[dict]:
        return list(self._entries)

    def load_recent(self, n: int = 20) -> list[dict]:
        return self._entries[-n:]

    def clear(self) -> None:
        self._entries.clear()

    @property
    def count(self) -> int:
        return len(self._entries)


class FileBackend:
    """JSON 文件后端。"""

    def __init__(self, file_path: Path) -> None:
        self.file_path = file_path
        self._ensure_file()

    def _ensure_file(self) -> None:
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.file_path.exists():
            write_text_file(self.file_path, "[]")

    def save(self, entry_dict: dict) -> None:
        entries = self.load_all()
        entries.append(entry_dict)
        self._write(entries)

    def load_all(self) -> list[dict]:
        try:
            loaded = read_json_file(self.file_path)
            if not loaded:
                return []
            if isinstance(loaded, list):
                return loaded
            return []
        except (ValueError, OSError) as exc:
            logger.warning(f"Failed to read history file {self.file_path}: {exc}")
            return []

    def load_recent(self, n: int = 20) -> list[dict]:
        all_entries = self.load_all()
        return all_entries[-n:] if n > 0 else all_entries

    def clear(self) -> None:
        write_text_file(self.file_path, "[]")

    def _write(self, entries: list[dict]) -> None:
        try:
            write_json_file(
                self.file_path,
                entries,
                ensure_ascii=False,
                indent=2,
            )
        except OSError as exc:
            logger.error(f"Failed to write history file: {exc}")

    @property
    def count(self) -> int:
        return len(self.load_all())


class SelfProgrammingHistory:
    """自我编程历史记录管理器。"""

    DEFAULT_FILENAME = ".self-programming-history.json"

    def __init__(
        self,
        storage_path: Path | None = None,
        in_memory: bool = False,
    ) -> None:
        if in_memory or storage_path is None:
            self.backend: MemoryBackend | FileBackend = MemoryBackend()
        else:
            self.backend = FileBackend(storage_path)

    def record(self, entry: HistoryEntry) -> None:
        self.backend.save(entry.to_dict())
        logger.debug(
            f"Recorded history: job={entry.job_id} "
            f"area={entry.target_area} status={entry.status.value}"
        )

    def record_from_job(self, job: Any, **overrides: Any) -> HistoryEntry:
        entry = HistoryEntry.from_job(job, **overrides)
        self.record(entry)
        return entry

    def get_recent(self, n: int = 20) -> list[HistoryEntry]:
        raw_list = self.backend.load_recent(n)
        return [self._dict_to_entry(d) for d in raw_list]

    def get_all(self) -> list[HistoryEntry]:
        raw_list = self.backend.load_all()
        return [self._dict_to_entry(d) for d in raw_list]

    def get_for_file(self, file_path: str) -> list[HistoryEntry]:
        all_entries = self.get_all()
        return [entry for entry in all_entries if file_path in entry.touched_files]

    def get_statistics(self) -> dict[str, Any]:
        return build_history_statistics(self.get_all())

    def clear(self) -> None:
        self.backend.clear()
        logger.info("Cleared all self-programming history")

    @property
    def count(self) -> int:
        return self.backend.count

    @staticmethod
    def _dict_to_entry(data: dict) -> HistoryEntry:
        restored = dict(data)
        if isinstance(restored.get("status"), str):
            restored["status"] = HistoryEntryStatus(restored["status"])
        return HistoryEntry(
            **{k: v for k, v in restored.items() if k in HistoryEntry.__dataclass_fields__}
        )


__all__ = [
    "HistoryEntryStatus",
    "HistoryEntry",
    "MemoryBackend",
    "FileBackend",
    "SelfProgrammingHistory",
]
