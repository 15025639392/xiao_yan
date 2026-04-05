"""
自编程历史记录 — 自编程能力的 Phase 4 核心之三

持久化存储所有自编程操作的历史，用于：
1. 冲突检测（查看最近修改了哪些文件）
2. 趋势分析（哪些模块最常被自编程修改）
3. 审计追踪（谁/何时/为什么做了什么改动）
4. 回滚定位（通过历史快速找到要回滚的 Job）

支持两种后端：
- 内存后端（默认，适合单次运行）
- JSON 文件后端（持久化，适合跨会话）
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# ── 数据模型 ────────────────────────────────────────────


class HistoryEntryStatus(str, Enum):
    """历史条目状态。"""

    APPLIED = "applied"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


@dataclass
class HistoryEntry:
    """一条完整的自编程历史记录。"""

    job_id: str
    target_area: str
    reason: str
    spec: str
    status: HistoryEntryStatus = HistoryEntryStatus.APPLIED
    patch_summary: str | None = None

    # 修改的文件列表
    touched_files: list[str] = field(default_factory=list)
    edits_summary: list[dict] = field(default_factory=list)  # 精简版 edits 信息

    # Git 信息
    branch_name: str | None = None
    commit_hash: str | None = None
    commit_message: str | None = None
    candidate_label: str | None = None

    # 多候选信息
    candidates_tried: int = 0  # 尝试了多少个候选
    selected_candidate: str | None = None  # 最终选中的

    # 沙箱预验证结果
    sandbox_prevalidated: bool = False
    sandbox_duration: float = 0.0

    # 冲突检测
    conflict_severity: str = "safe"
    conflict_count: int = 0

    # 时间戳
    created_at: str = ""   # ISO format
    completed_at: str = ""

    def __post_init__(self) -> None:
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()
        if not self.completed_at and self.status != HistoryEntryStatus.APPLIED:
            self.completed_at = datetime.now(timezone.utc).isoformat()

    @classmethod
    def from_job(cls, job: Any, **overrides) -> "HistoryEntry":
        """从 SelfImprovementJob 创建历史条目。"""
        status_map = {
            "applied": HistoryEntryStatus.APPLIED,
            "failed": HistoryEntryStatus.FAILED,
        }

        # 精简 edits 信息
        edits_summary = []
        for e in (job.edits or []):
            kind_val = getattr(e, 'kind', 'replace')
            if hasattr(kind_val, 'value'):
                kind_str = kind_val.value
            else:
                kind_str = str(kind_val)
            edits_summary.append({
                "file": getattr(e, 'file_path', ''),
                "kind": kind_str,
                "search": (getattr(e, 'search_text', '') or "")[:60],
            })

        return cls(
            job_id=job.id,
            target_area=job.target_area,
            reason=job.reason,
            spec=job.spec,
            status=status_map.get(job.status, HistoryEntryStatus.FAILED),
            patch_summary=job.patch_summary,
            touched_files=list(job.touched_files or []),
            edits_summary=edits_summary,
            branch_name=job.branch_name,
            commit_hash=job.commit_hash,
            commit_message=job.commit_message,
            candidate_label=job.candidate_label,
            created_at=datetime.now(timezone.utc).isoformat(),
            **overrides,
        )

    def to_dict(self) -> dict:
        """序列化为字典。"""
        d = asdict(self)
        # 处理枚举
        d['status'] = self.status.value
        return d


# ── 存储后端 ────────────────────────────────────────────


class MemoryBackend:
    """内存后端——数据保存在 RAM 中，进程退出即丢失。

    适合测试和短期运行。
    """

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
    """JSON 文件后端——数据持久化到磁盘。

    适合生产环境和跨会话审计。
    """

    def __init__(self, file_path: Path) -> None:
        """
        Args:
            file_path: JSON 文件的路径
        """
        self.file_path = file_path
        self._ensure_file()

    def _ensure_file(self) -> None:
        """确保文件存在且是有效 JSON。"""
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.file_path.exists():
            self.file_path.write_text("[]", encoding="utf-8")

    def save(self, entry_dict: dict) -> None:
        entries = self.load_all()
        entries.append(entry_dict)
        self._write(entries)

    def load_all(self) -> list[dict]:
        try:
            raw = self.file_path.read_text(encoding="utf-8").strip()
            if not raw:
                return []
            return json.loads(raw)
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning(f"Failed to read history file {self.file_path}: {exc}")
            return []

    def load_recent(self, n: int = 20) -> list[dict]:
        all_entries = self.load_all()
        return all_entries[-n:] if n > 0 else all_entries

    def clear(self) -> None:
        self.file_path.write_text("[]", encoding="utf-8")

    def _write(self, entries: list[dict]) -> None:
        try:
            self.file_path.write_text(
                json.dumps(entries, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except OSError as exc:
            logger.error(f"Failed to write history file: {exc}")

    @property
    def count(self) -> int:
        return len(self.load_all())


# ── 主类 ────────────────────────────────────────────────


class SelfImprovementHistory:
    """自编程历史记录管理器。

    用法::

        history = SelfImprovementHistory(workspace_root / ".self-improvement-history.json")
        history.record_from_job(applied_job)

        recent = history.get_recent(10)
        stats = history.get_statistics()
    """

    DEFAULT_FILENAME = ".self-improvement-history.json"

    def __init__(
        self,
        storage_path: Path | None = None,
        in_memory: bool = False,
    ) -> None:
        """
        Args:
            storage_path: 文件后端的路径（None 则用默认位置）
            in_memory: True 表示仅使用内存后端（不写磁盘）
        """
        if in_memory or storage_path is None:
            self.backend: MemoryBackend | FileBackend = MemoryBackend()
        else:
            self.backend = FileBackend(storage_path)

    def record(self, entry: HistoryEntry) -> None:
        """记录一条历史。"""
        self.backend.save(entry.to_dict())
        logger.debug(
            f"Recorded history: job={entry.job_id} "
            f"area={entry.target_area} status={entry.status.value}"
        )

    def record_from_job(self, job: Any, **overrides) -> HistoryEntry:
        """从 Job 创建并记录一条历史。返回创建的 Entry。"""
        entry = HistoryEntry.from_job(job, **overrides)
        self.record(entry)
        return entry

    def get_recent(self, n: int = 20) -> list[HistoryEntry]:
        """获取最近 N 条历史记录。"""
        raw_list = self.backend.load_recent(n)
        return [self._dict_to_entry(d) for d in raw_list]

    def get_all(self) -> list[HistoryEntry]:
        """获取全部历史记录。"""
        raw_list = self.backend.load_all()
        return [self._dict_to_entry(d) for d in raw_list]

    def get_for_file(self, file_path: str) -> list[HistoryEntry]:
        """获取涉及指定文件的全部历史记录。"""
        all_entries = self.get_all()
        return [e for e in all_entries if file_path in e.touched_files]

    def get_statistics(self) -> dict[str, Any]:
        """生成统计摘要。"""
        all_entries = self.get_all()

        total = len(all_entries)
        applied = sum(1 for e in all_entries if e.status == HistoryEntryStatus.APPLIED)
        failed = sum(1 for e in all_entries if e.status == HistoryEntryStatus.FAILED)

        # 按目标区域统计
        area_counts: dict[str, int] = {}
        for e in all_entries:
            area_counts[e.target_area] = area_counts.get(e.target_area, 0) + 1

        # 最常被修改的文件
        file_counts: dict[str, int] = {}
        for e in all_entries:
            for fp in e.touched_files:
                file_counts[fp] = file_counts.get(fp, 0) + 1

        top_files = sorted(file_counts.items(), key=lambda x: x[1], reverse=True)[:10]

        # 涉及沙箱预验证的比例
        sandbox_used = sum(1 for e in all_entries if e.sandbox_prevalidated)
        sandbox_rate = sandbox_used / total * 100 if total > 0 else 0.0

        # 有冲突告警的比例
        conflict_count = sum(1 for e in all_entries if e.conflict_count > 0)
        conflict_rate = conflict_count / total * 100 if total > 0 else 0.0

        return {
            "total_jobs": total,
            "applied": applied,
            "failed": failed,
            "success_rate": round(applied / total * 100, 1) if total > 0 else 0.0,
            "by_target_area": area_counts,
            "most_modified_files": top_files,
            "sandbox_usage_rate": round(sandbox_rate, 1),
            "conflict_alert_rate": round(conflict_rate, 1),
            "multi_candidate_usage": sum(1 for e in all_entries if e.candidates_tried > 1),
        }

    def clear(self) -> None:
        """清除全部历史。"""
        self.backend.clear()
        logger.info("Cleared all improvement history")

    @property
    def count(self) -> int:
        return self.backend.count

    @staticmethod
    def _dict_to_entry(d: dict) -> HistoryEntry:
        """从字典还原为 HistoryEntry。"""
        # 处理 status 枚举
        if isinstance(d.get('status'), str):
            d['status'] = HistoryEntryStatus(d['status'])
        return HistoryEntry(**{k: v for k, v in d.items() if k in HistoryEntry.__dataclass_fields__})
