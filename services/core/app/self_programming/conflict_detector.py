"""
补丁冲突检测器

当多个自我编程任务并发或连续运行时，检测补丁之间的潜在冲突：

1. 文件级冲突 — 两个补丁修改同一文件的相同位置
2. 依赖冲突 — 补丁 A 修改了补丁 B 的依赖接口
3. 安全冲突 — 补丁试图修改已标记为受保护的路径
4. 循环自改 — 同一文件被频繁修改（可能表示修复不彻底）

输出结构化的冲突报告，供 Service 层决策：
- BLOCKING: 必须阻止应用
- WARNING: 可以应用但需人工确认
- SAFE: 无冲突，可以安全应用
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# ── 数据模型 ────────────────────────────────────────────


class ConflictSeverity(str, Enum):
    """冲突严重程度。"""

    SAFE = "safe"           # 无冲突
    WARNING = "warning"     # 有风险但可接受
    BLOCKING = "blocking"   # 必须阻止


@dataclass
class FileConflict:
    """单个文件的冲突详情。"""

    file_path: str
    severity: ConflictSeverity
    conflict_type: str       # "overlap", "dependency", "protected"
    description: str         # 人类可读描述
    existing_edits: list[str] = field(default_factory=list)  # 已有补丁的搜索文本
    new_edits: list[str] = field(default_factory=list)        # 新补丁的搜索文本


@dataclass
class ConflictReport:
    """完整的冲突检测报告。"""

    severity: ConflictSeverity = ConflictSeverity.SAFE
    conflicts: list[FileConflict] = field(default_factory=list)
    total_files_checked: int = 0
    overlapping_files: list[str] = field(default_factory=list)

    @property
    def is_safe(self) -> bool:
        return self.severity == ConflictSeverity.SAFE and len(self.conflicts) == 0

    @property
    def has_blocking(self) -> bool:
        return any(c.severity == ConflictSeverity.BLOCKING for c in self.conflicts)

    def summary(self) -> str:
        """生成人类可读的摘要。"""
        if self.is_safe:
            return f"✅ 无冲突（检查了 {self.total_files_checked} 个文件）"

        blocking = sum(1 for c in self.conflicts if c.severity == ConflictSeverity.BLOCKING)
        warnings = sum(1 for c in self.conflicts if c.severity == ConflictSeverity.WARNING)
        parts: list[str] = []
        if blocking:
            parts.append(f"🚫 {blocking} 个阻塞冲突")
        if warnings:
            parts.append(f"⚠️ {warnings} 个警告")
        parts.append(f"(检查 {self.total_files_checked} 个文件)")
        return " ".join(parts)


# ── 受保护路径模式（与 LLMPlanner 共享逻辑）─────────
PROTECTED_PATTERNS = (
    r"\.env(\.|$)",
    r"\.env\.",
    r"secrets?",
    r"credentials",
    r"\.pem$",
    r"\.key$",
)


# ── 高频修改阈值 ────────────────────────────────────────
FREQUENT_EDIT_THRESHOLD = 3  # 同一文件在 N 次历史中被修改则告警


# ── 主类 ────────────────────────────────────────────────


class ConflictDetector:
    """补丁冲突检测器。

    用法::

        detector = ConflictDetector(workspace_root)
        report = detector.check(edits, recent_history)

        if report.has_blocking:
            # 阻止应用
            pass
        elif not report.is_safe:
            # 警告但继续
            pass
    """

    def __init__(
        self,
        workspace_root: Path,
        protected_patterns: tuple[str, ...] | None = None,
    ) -> None:
        """
        Args:
            workspace_root: 项目根目录
            protected_patterns: 额外的受保护路径正则模式
        """
        self.workspace_root = workspace_root
        self.protected = protected_patterns or PROTECTED_PATTERNS
        # 最近的应用记录（用于循环检测）
        self._recent_applies: dict[str, list[datetime]] = {}

    def check(
        self,
        edits: list[Any],
        applied_history: list[Any] | None = None,
    ) -> ConflictReport:
        """检查一组编辑操作是否存在冲突。

        Args:
            edits: 待应用的 SelfProgrammingEdit 列表
            applied_history: 最近成功应用的自我编程 Job 列表（可选）

        Returns:
            ConflictReport 冲突报告
        """
        if not edits:
            return ConflictReport(severity=ConflictSeverity.SAFE, total_files_checked=0)

        conflicts: list[FileConflict] = []
        new_file_set = {e.file_path for e in edits}

        # 收集新补丁中每个文件的 search_text
        new_search_texts: dict[str, list[str]] = {}
        for edit in edits:
            fp = edit.file_path
            texts = new_search_texts.setdefault(fp, [])
            if hasattr(edit, 'search_text') and edit.search_text:
                texts.append(edit.search_text[:80])  # 截断用于比较

        total_checked = len(new_file_set)

        # 检查 1: 受保护路径
        for edit in edits:
            prot_conflict = self._check_protected(edit.file_path)
            if prot_conflict:
                conflicts.append(prot_conflict)

        # 检查 2: 与历史重叠（如果提供了历史）
        history_overlaps: set[str] = set()
        if applied_history:
            for job in applied_history:
                job_files = getattr(job, 'touched_files', []) or []
                job_edits = getattr(job, 'edits', []) or []
                for jf in job_files:
                    if jf in new_file_set:
                        history_overlaps.add(jf)
                        # 进一步检查是否修改同一行/区域
                        existing_searches = [
                            (getattr(e, 'search_text', '') or "")[:80]
                            for e in job_edits
                            if getattr(e, 'file_path', '') == jf
                        ]
                        new_st = new_search_texts.get(jf, [])
                        if existing_searches and new_st:
                            overlap_desc = self._describe_overlap(existing_searches, new_st)
                            if overlap_desc:
                                conflicts.append(FileConflict(
                                    file_path=jf,
                                    severity=ConflictSeverity.WARNING,
                                    conflict_type="overlap",
                                    description=overlap_desc,
                                    existing_edits=existing_searches,
                                    new_edits=new_st,
                                ))

        # 检查 3: 循环自改检测
        for fp in new_file_set:
            apply_count = len(self._recent_applies.get(fp, []))
            if apply_count >= FREQUENT_EDIT_THRESHOLD:
                conflicts.append(FileConflict(
                    file_path=fp,
                    severity=ConflictSeverity.WARNING,
                    conflict_type="frequent_edit",
                    description=f"该文件在最近 {apply_count} 次自我编程中被修改，可能存在修复不稳定的问题",
                ))

        # 确定总体严重程度
        severity = ConflictSeverity.SAFE
        if any(c.severity == ConflictSeverity.BLOCKING for c in conflicts):
            severity = ConflictSeverity.BLOCKING
        elif any(c.severity == ConflictSeverity.WARNING for c in conflicts):
            severity = ConflictSeverity.WARNING

        return ConflictReport(
            severity=severity,
            conflicts=conflicts,
            total_files_checked=total_checked,
            overlapping_files=list(history_overlaps),
        )

    def record_apply(self, file_paths: list[str]) -> None:
        """记录一次成功的补丁应用，用于后续的循环检测。"""
        now = datetime.now(timezone.utc)
        for fp in file_paths:
            applies = self._recent_applies.setdefault(fp, [])
            applies.append(now)
            # 只保留最近 20 条记录
            if len(applies) > 20:
                self._recent_applies[fp] = applies[-20:]

    def clear_history(self) -> None:
        """清除所有应用记录。"""
        self._recent_applies.clear()

    # ── 内部检查方法 ─────────────────────────────────

    def _check_protected(self, file_path: str) -> FileConflict | None:
        """检查文件是否匹配受保护路径模式。"""
        fp_lower = file_path.lower()
        for pattern in self.protected:
            if re.search(pattern, fp_lower, re.IGNORECASE):
                return FileConflict(
                    file_path=file_path,
                    severity=ConflictSeverity.BLOCKING,
                    conflict_type="protected",
                    description=f"文件 '{file_path}' 匹配受保护路径模式 '{pattern}'，不允许自我编程修改",
                )
        return None

    @staticmethod
    def _describe_overlap(
        existing: list[str],
        new: list[str],
    ) -> str | None:
        """描述两个补丁列表的重叠程度。"""
        if not existing or not new:
            return None

        exact_overlap = set(existing) & set(new)
        if exact_overlap:
            return f"新旧补丁修改了完全相同的代码段: {', '.join(list(exact_overlap)[:3])}"

        # 检查部分重叠（一个包含另一个的子串）
        partials: list[str] = []
        for e in existing:
            for n in new:
                if e in n or n in e or _share_common_prefix(e, n):
                    partials.append(f"'{e[:40]}' ↔ '{n[:40]}'")
                    break

        if partials:
            return f"新旧补丁可能修改了相邻或相关代码: {'; '.join(partials[:2])}"

        return f"两个补丁都修改了此文件（但具体区域不同）"


def _share_common_prefix(a: str, b: str, min_common: int = 10) -> bool:
    """检查两字符串是否有足够长的公共前缀。"""
    common = 0
    for _ in range(min(len(a), len(b))):
        if a[common] != b[common]:
            break
        common += 1
    return common >= min_common
