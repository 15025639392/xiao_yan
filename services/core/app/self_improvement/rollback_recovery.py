"""
回滚恢复管理器 — 自编程能力的 Phase 5 核心之一

当自编程补丁导致问题时，提供精细化的回滚和恢复能力：

1. 差异快照 — 每次 apply 前记录文件级 diff（修改前/后内容）
2. 安全回滚 — 逐文件精确还原，比 git reset 更可控
3. 级联回滚 — 检测依赖关系，回滚基础补丁时提示后续影响
4. 回滚验证 — 回滚后自动运行测试确认系统恢复
5. 回滚报告 — 记录原因、影响范围、后续建议

与 GitWorkflowManager 的关系：
- Git 负责版本控制层面的 commit/branch 管理
- RollbackRecovery 负责文件内容层面的精确还原和验证
- 两者互补：Git 做粗粒度回滚，Recovery 做细粒度恢复
"""

from __future__ import annotations

import hashlib
import logging
import subprocess
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)


# ── 数据模型 ────────────────────────────────────────────


class RollbackReason(str, Enum):
    """触发回滚的原因。"""

    VERIFICATION_FAILED = "verification_failed"
    HEALTH_DEGRADED = "health_degraded"
    MANUAL_REQUEST = "manual_request"
    CASCADE_DEPENDENCY = "cascade_dependency"
    SANDBOX_MISMATCH = "sandbox_mismatch"


class RollbackStatus(str, Enum):
    """回滚操作状态。"""

    SUCCESS = "success"
    PARTIAL = "partial"       # 部分文件回滚成功
    FAILED = "failed"
    SKIPPED = "skipped"       # 无需回滚（没有变更）


@dataclass(frozen=True)
class DiffSnapshot:
    """单个文件的修改前后快照。

    在 apply 之前捕获，用于后续精确回滚。
    """

    file_path: str              # 相对路径
    original_content: str       # 修改前的原始内容
    original_hash: str          # 原始内容的 SHA256（用于校验）
    timestamp: str = ""         # ISO 格式时间戳
    file_existed: bool = True   # 文件是否已存在（CREATE kind 为 False）

    def __post_init__(self) -> None:
        if not self.timestamp:
            object.__setattr__(self, "timestamp", datetime.now(timezone.utc).isoformat())

    @property
    def content_hash(self) -> str:
        """计算原始内容的哈希值。"""
        return hashlib.sha256(self.original_content.encode("utf-8")).hexdigest()

    @classmethod
    def from_path(cls, file_path: str | Path, workspace_root: Path) -> DiffSnapshot:
        """从工作区中的文件创建快照。

        Args:
            file_path: 文件的相对或绝对路径
            workspace_root: 工作区根目录

        Returns:
            捕获的文件快照
        """
        rel_path = Path(file_path).as_posix()
        if Path(file_path).is_absolute():
            try:
                rel_path = Path(file_path).relative_to(workspace_root).as_posix()
            except ValueError:
                pass

        full_path = workspace_root / rel_path
        if full_path.exists():
            content = full_path.read_text(encoding="utf-8")
            return cls(
                file_path=rel_path,
                original_content=content,
                original_hash=hashlib.sha256(content.encode("utf-8")).hexdigest(),
                file_existed=True,
            )
        return cls(
            file_path=rel_path,
            original_content="",
            original_hash="",
            file_existed=False,
        )


@dataclass
class RollbackPlan:
    """回滚计划 — 描述一次回滚操作的全部步骤。"""

    job_id: str
    reason: RollbackReason
    reason_detail: str = ""
    snapshots: list[DiffSnapshot] = field(default_factory=list)
    affected_files: list[str] = field(default_factory=list)
    dependent_job_ids: list[str] = field(default_factory=list)   # 级联影响的 Job
    created_at: str = ""

    def __post_init__(self) -> None:
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()
        if not self.affected_files and self.snapshots:
            self.affected_files = [s.file_path for s in self.snapshots]

    @property
    def summary(self) -> str:
        """人类可读的计划摘要。"""
        emoji_map = {
            RollbackReason.VERIFICATION_FAILED: "🔴",
            RollbackReason.HEALTH_DEGRADED: "📉",
            RollbackReason.MANUAL_REQUEST: "👤",
            RollbackReason.CASCADE_DEPENDENCY: "🔗",
            RollbackReason.SANDBOX_MISMATCH: "⚠️",
        }
        emoji = emoji_map.get(self.reason, "🔄")
        dep_note = f", 级联影响 {len(self.dependent_job_ids)} 个后续 Job" if self.dependent_job_ids else ""
        return f"{emoji} 回滚计划 [{self.job_id[:12]}]: {self.reason.value}{dep_note}, 影响 {len(self.affected_files)} 个文件"


@dataclass
class RollbackResult:
    """回滚执行结果。"""

    status: RollbackStatus
    plan: RollbackPlan
    restored_files: list[str] = field(default_factory=list)
    failed_files: list[str] = field(default_factory=list)
    verification_passed: bool | None = None     # None 表示未运行验证
    verification_output: str = ""
    duration_seconds: float = 0.0
    rolled_back_at: str = ""
    recommendation: str = ""                      # 后续建议

    def __post_init__(self) -> None:
        if not self.rolled_back_at and self.status != RollbackStatus.SKIPPED:
            object.__setattr__(self, "rolled_back_at", datetime.now(timezone.utc).isoformat())

    @property
    def summary(self) -> str:
        """人类可读的结果摘要。"""
        status_emoji = {
            RollbackStatus.SUCCESS: "✅",
            RollbackStatus.PARTIAL: "⚠️",
            RollbackStatus.FAILED: "❌",
            RollbackStatus.SKIPPED: "➡️",
        }
        emoji = status_emoji.get(self.status, "?")
        parts = [f"{emoji} 回滚 {self.status.value}"]
        if self.restored_files:
            parts.append(f"还原 {len(self.restored_files)} 文件")
        if self.failed_files:
            parts.append(f"失败 {len(self.failed_files)} 文件")
        if self.verification_passed is True:
            parts.append("验证通过 ✓")
        elif self.verification_passed is False:
            parts.append("验证未通过 ✗")
        return " | ".join(parts)


# ── 主类 ────────────────────────────────────────────────


class RollbackRecovery:
    """回滚恢复管理器。

    用法::

        recovery = RollbackRecovery(workspace_root)

        # 1. 在 apply 前创建快照
        snapshots = recovery.snapshot_before_apply(job)

        # 2. 如果需要回滚，先制定计划
        plan = recovery.create_rollback_plan(job_id="abc", reason=RollbackReason.HEALTH_DEGRADED)

        # 3. 执行回滚
        result = recovery.execute_rollback(plan)

        # 4. 验证回滚后的稳定性
        if result.verification_passed:
            print("系统已恢复正常")
    """

    # 快照保留上限
    MAX_SNAPSHOTS_PER_JOB = 50
    # 最大级联深度
    MAX_CASCADE_DEPTH = 5

    def __init__(
        self,
        workspace_root: Path,
        auto_snapshot: bool = True,
        verify_after_rollback: bool = True,
    ) -> None:
        """
        Args:
            workspace_root: 项目根目录
            auto_snapshot: 是否在 snapshot_before_apply 时自动持久化
            verify_after_rollback: 执行回滚后是否自动跑验证命令
        """
        self.workspace_root = workspace_root
        self.auto_snapshot = auto_snapshot
        self.verify_after_rollback = verify_after_rollback

        # Job ID → 快照列表（一个 Job 可能有多组快照，如果重试的话）
        self._snapshots: dict[str, list[DiffSnapshot]] = {}

        # 回滚历史
        self._rollback_history: list[RollbackResult] = []

    # ── 快照 API ─────────────────────────────────

    def snapshot_before_apply(
        self,
        job: Any,
        extra_files: list[str] | None = None,
    ) -> list[DiffSnapshot]:
        """在应用补丁前创建差异快照。

        Args:
            job: 待执行的 SelfImprovementJob（提取 touched_files 和 edits）
            extra_files: 额外需要快照的文件路径

        Returns:
            创建的快照列表
        """
        # 收集所有需要快照的文件
        file_set: set[str] = set()

        # 从 Job 的 touched_files 收集
        touched = getattr(job, 'touched_files', None) or []
        for fp in touched:
            file_set.add(fp)

        # 从 Job 的 edits 中收集
        edits = getattr(job, 'edits', None) or []
        for edit in edits:
            fp = getattr(edit, 'file_path', None)
            if fp:
                file_set.add(fp)

        # 额外文件
        if extra_files:
            file_set.update(extra_files)

        # 创建快照
        snapshots: list[DiffSnapshot] = []
        for fp in sorted(file_set):
            snap = DiffSnapshot.from_path(fp, self.workspace_root)
            snapshots.append(snap)

        # 存储
        job_id = getattr(job, 'id', 'unknown')
        if job_id not in self._snapshots:
            self._snapshots[job_id] = []

        existing_count = len(self._snapshots[job_id])
        if existing_count < self.MAX_SNAPSHOTS_PER_JOB:
            self._snapshots[job_id].extend(snapshots)
        else:
            logger.warning(
                f"Snapshot limit reached for job {job_id} "
                f"({existing_count} >= {self.MAX_SNAPSHOTS_PER_JOB})"
            )

        logger.debug(
            f"Created {len(snapshots)} snapshots for job {job_id[:12]}..."
        )
        return snapshots

    def get_snapshots(self, job_id: str) -> list[DiffSnapshot]:
        """获取指定 Job 的所有快照。"""
        return list(self._snapshots.get(job_id, []))

    def has_snapshot(self, job_id: str) -> bool:
        """检查是否有某 Job 的快照。"""
        return job_id in self._snapshots and len(self._snapshots[job_id]) > 0

    def clear_snapshots(self, job_id: str | None = None) -> None:
        """清除快照。

        Args:
            job_id: 指定 Job ID 只删该 Job 的，None 则全部清除。
        """
        if job_id:
            self._snapshots.pop(job_id, None)
        else:
            self._snapshots.clear()

    # ── 回滚规划 API ───────────────────────────────

    def create_rollback_plan(
        self,
        job_id: str,
        reason: RollbackReason,
        reason_detail: str = "",
        dependent_job_ids: list[str] | None = None,
    ) -> RollbackPlan:
        """为指定 Job 创建回滚计划。

        Args:
            job_id: 要回滚的自编程任务 ID
            reason: 回滚原因
            reason_detail: 详细说明
            dependent_job_ids: 受级联影响的后续 Job 列表

        Returns:
            回滚计划
        """
        snapshots = self.get_snapshots(job_id)

        if not snapshots:
            logger.warning(f"No snapshots found for job {job_id}, creating empty rollback plan")
            return RollbackPlan(
                job_id=job_id,
                reason=reason,
                reason_detail=reason_detail or "无快照可用，将尝试从 Git 恢复",
                dependent_job_ids=dependent_job_ids or [],
            )

        plan = RollbackPlan(
            job_id=job_id,
            reason=reason,
            reason_detail=reason_detail,
            snapshots=snapshots,
            dependent_job_ids=dependent_job_ids or [],
        )

        logger.info(f"Created rollback plan: {plan.summary}")
        return plan

    def detect_cascade_dependencies(
        self,
        job_id: str,
        applied_history: list[Any] | None = None,
    ) -> list[str]:
        """检测级联依赖 — 找出在目标 Job 之后修改了相同文件的后续 Job。

        Args:
            job_id: 要回滚的目标 Job ID
            applied_history: 最近成功应用的 Job 历史（按时间排序）

        Returns:
            受级联影响的后续 Job ID 列表
        """
        target_snaps = self.get_snapshots(job_id)
        target_files = {s.file_path for s in target_snaps}

        if not target_files or not applied_history:
            return []

        dependents: list[str] = []
        target_index = -1

        # 找到目标 Job 在历史中的位置
        for idx, job in enumerate(applied_history):
            jid = getattr(job, 'id', '') or getattr(job, 'job_id', '')
            if jid == job_id:
                target_index = idx
                break

        if target_index == -1:
            # 目标不在历史中，检查所有后续 Job
            check_from = 0
        else:
            check_from = target_index + 1

        # 检查之后的 Job 是否修改了相同文件
        for job in applied_history[check_from:]:
            job_files = set(getattr(job, 'touched_files', []) or [])
            if target_files & job_files:
                jid = getattr(job, 'id', '') or getattr(job, 'job_id', '')
                if jid and jid != job_id:
                    dependents.append(jid)

        return dependents

    # ── 回滚执行 API ───────────────────────────────

    def execute_rollback(
        self,
        plan: RollbackPlan,
        verification_commands: list[str] | None = None,
    ) -> RollbackResult:
        """执行回滚计划。

        逐个文件还原到快照时的内容：
        - 原本存在的文件 → 还原原始内容
        - CREATE 操作新建的文件 → 删除

        Args:
            plan: 回滚计划
            verification_commands: 回滚后要运行的验证命令（可选）

        Returns:
            回滚结果
        """
        import time

        start_time = time.monotonic()
        restored: list[str] = []
        failed: list[str] = []

        if not plan.snapshots:
            logger.warning(f"Empty rollback plan for job {plan.job_id}, skipping")
            return RollbackResult(
                status=RollbackStatus.SKIPPED,
                plan=plan,
                recommendation="无快照可用，建议使用 Git 回滚：git checkout -- . 或 git reset --hard HEAD~1",
            )

        for snapshot in plan.snapshots:
            try:
                full_path = self.workspace_root / snapshot.file_path

                if snapshot.file_existed:
                    # 文件原本存在 → 还原原始内容
                    # 校验当前文件是否被意外篡改（非本次自编程改动的部分）
                    if full_path.exists():
                        current_content = full_path.read_text(encoding="utf-8")
                        full_path.write_text(snapshot.original_content, encoding="utf-8")
                        restored.append(snapshot.file_path)
                        logger.debug(f"Restored: {snapshot.file_path}")
                    else:
                        # 文件被删除了，重新创建
                        full_path.parent.mkdir(parents=True, exist_ok=True)
                        full_path.write_text(snapshot.original_content, encoding="utf-8")
                        restored.append(snapshot.file_path)
                        logger.debug(f"Re-created: {snapshot.file_path}")
                else:
                    # 文件是本次自编程新建的 → 删除
                    if full_path.exists():
                        full_path.unlink()
                        restored.append(snapshot.file_path)
                        logger.debug(f"Deleted (was created by patch): {snapshot.file_path}")
                    else:
                        # 已经不存在了，也算成功
                        restored.append(snapshot.file_path)

            except Exception as exc:
                failed.append(snapshot.file_path)
                logger.error(f"Failed to restore {snapshot.file_path}: {exc}")

        # 确定状态
        if failed and restored:
            status = RollbackStatus.PARTIAL
        elif failed:
            status = RollbackStatus.FAILED
        else:
            status = RollbackStatus.SUCCESS

        elapsed = time.monotonic() - start_time

        # 可选的验证步骤
        verification_passed: bool | None = None
        verification_output = ""

        if self.verify_after_rollback and verification_commands and restored:
            verification_passed, verification_output = self._run_verification(verification_commands)

        # 生成建议
        recommendation = self._generate_recommendation(status, plan, restored, failed, verification_passed)

        result = RollbackResult(
            status=status,
            plan=plan,
            restored_files=restored,
            failed_files=failed,
            verification_passed=verification_passed,
            verification_output=verification_output,
            duration_seconds=elapsed,
            recommendation=recommendation,
        )

        # 记录到历史
        self._rollback_history.append(result)
        logger.info(f"Rollback completed: {result.summary}")

        return result

    def smart_rollback(
        self,
        job_id: str,
        reason: RollbackReason,
        reason_detail: str = "",
        verification_commands: list[str] | None = None,
        applied_history: list[Any] | None = None,
    ) -> RollbackResult:
        """一站式智能回滚：检测依赖 → 制定计划 → 执行。

        Args:
            job_id: 要回滚的 Job ID
            reason: 回滚原因
            reason_detail: 详细说明
            verification_commands: 验证命令
            applied_history: 应用历史（用于级联检测）

        Returns:
            回滚结果
        """
        # 检测级联依赖
        dependencies = []
        if applied_history:
            dependencies = self.detect_cascade_dependencies(job_id, applied_history)

        # 制定计划
        plan = self.create_rollback_plan(
            job_id=job_id,
            reason=reason,
            reason_detail=reason_detail,
            dependent_job_ids=dependencies,
        )

        # 执行
        return self.execute_rollback(plan, verification_commands=verification_commands)

    # ── 查询 API ──────────────────────────────────

    def get_rollback_history(self, limit: int = 20) -> list[RollbackResult]:
        """获取回滚历史记录。"""
        return list(self._rollback_history[-limit:])

    def get_rollback_statistics(self) -> dict[str, Any]:
        """获取回滚统计信息。"""
        history = self._rollback_history
        total = len(history)
        if total == 0:
            return {"total_rollbacks": 0}

        by_reason: dict[str, int] = {}
        by_status: dict[str, int] = {}
        total_restored = 0
        total_failed = 0
        verification_pass_rate = 0
        verified_count = 0

        for r in history:
            reason_key = r.plan.reason.value
            by_reason[reason_key] = by_reason.get(reason_key, 0) + 1
            status_key = r.status.value
            by_status[status_key] = by_status.get(status_key, 0) + 1
            total_restored += len(r.restored_files)
            total_failed += len(r.failed_files)
            if r.verification_passed is not None:
                verified_count += 1
                if r.verification_passed:
                    verification_pass_rate += 1

        return {
            "total_rollbacks": total,
            "by_reason": by_reason,
            "by_status": by_status,
            "total_files_restored": total_restored,
            "total_files_failed": total_failed,
            "verification_pass_rate": (
                round(verification_pass_rate / verified_count * 100, 1)
                if verified_count > 0
                else None
            ),
        }

    # ── 内部方法 ──────────────────────────────────

    def _run_verification(
        self,
        commands: list[str],
    ) -> tuple[bool, str]:
        """运行验证命令，返回 (是否通过, 输出文本)。"""
        outputs: list[str] = []
        all_passed = True

        for cmd in commands:
            try:
                result = subprocess.run(
                    cmd,
                    shell=True,
                    cwd=self.workspace_root,
                    capture_output=True,
                    text=True,
                    timeout=60,
                    env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
                )
                combined = (result.stdout or "").strip() + "\n" + (result.stderr or "").strip()
                outputs.append(f"$ {cmd}\n{combined}".strip())
                if result.returncode != 0:
                    all_passed = False
                    break
            except subprocess.TimeoutExpired:
                outputs.append(f"$ [TIMEOUT] {cmd}")
                all_passed = False
                break
            except Exception as exc:
                outputs.append(f"$ [ERROR] {cmd} → {exc}")
                all_passed = False
                break

        return all_passed, "\n\n".join(outputs)

    @staticmethod
    def _generate_recommendation(
        status: RollbackStatus,
        plan: RollbackPlan,
        restored: list[str],
        failed: list[str],
        verification_passed: bool | None,
    ) -> str:
        """根据回滚结果生成后续建议。"""
        parts: list[str] = []

        if status == RollbackStatus.SUCCESS:
            parts.append("回滚成功，系统应已恢复到补丁前的状态。")
            if plan.dependent_job_ids:
                parts.append(
                    f"注意：有 {len(plan.dependent_job_ids)} 个后续 Job 可能受影响，建议检查是否需要一并回滚。"
                )
        elif status == RollbackStatus.PARTIAL:
            parts.append(f"部分回滚成功。{len(failed)} 个文件还原失败：{', '.join(failed)}")
            parts.append("建议手动检查这些文件的完整性。")
        elif status == RollbackStatus.FAILED:
            parts.append("回滚全部失败。建议使用 Git 进行粗粒度恢复：")
            parts.append("  git checkout -- .      # 丢弃未提交更改")
            parts.append("  git reset --hard HEAD~1  # 回退最后一个 commit")

        if verification_passed is False:
            parts.append("回滚后验证仍未通过，问题可能不在此补丁中，或原始代码本身就有缺陷。")
        elif verification_passed is True:
            parts.append("回滚后验证通过，确认系统已恢复健康状态。")

        return "\n".join(parts)
