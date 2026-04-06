"""
回滚恢复管理器。

保持向后兼容：
- 对外数据模型仍从本模块导出（RollbackReason/Status/Plan/Result/DiffSnapshot）
- RollbackRecovery 的公开方法和语义不变
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

from app.self_programming.rollback_models import (
    DiffSnapshot,
    RollbackPlan,
    RollbackReason,
    RollbackResult,
    RollbackStatus,
)
from app.self_programming.rollback_ops import (
    build_rollback_recommendation,
    build_rollback_statistics,
    collect_snapshot_files,
    compute_rollback_status,
    detect_dependent_jobs,
    restore_from_snapshots,
    run_post_rollback_verification,
    take_diff_snapshots,
)

logger = logging.getLogger(__name__)


class RollbackRecovery:
    """回滚恢复管理器。"""

    MAX_SNAPSHOTS_PER_JOB = 50
    MAX_CASCADE_DEPTH = 5

    def __init__(
        self,
        workspace_root: Path,
        auto_snapshot: bool = True,
        verify_after_rollback: bool = True,
    ) -> None:
        self.workspace_root = workspace_root
        self.auto_snapshot = auto_snapshot
        self.verify_after_rollback = verify_after_rollback
        self._snapshots: dict[str, list[DiffSnapshot]] = {}
        self._rollback_history: list[RollbackResult] = []

    # ── 快照 API ─────────────────────────────────

    def snapshot_before_apply(
        self,
        job: Any,
        extra_files: list[str] | None = None,
    ) -> list[DiffSnapshot]:
        file_set = collect_snapshot_files(job, extra_files)
        snapshots = take_diff_snapshots(self.workspace_root, file_set)

        job_id = getattr(job, "id", "unknown")
        if job_id not in self._snapshots:
            self._snapshots[job_id] = []

        existing_count = len(self._snapshots[job_id])
        if existing_count < self.MAX_SNAPSHOTS_PER_JOB:
            self._snapshots[job_id].extend(snapshots)
        else:
            logger.warning(
                "Snapshot limit reached for job %s (%d >= %d)",
                job_id,
                existing_count,
                self.MAX_SNAPSHOTS_PER_JOB,
            )

        logger.debug("Created %d snapshots for job %s...", len(snapshots), job_id[:12])
        return snapshots

    def get_snapshots(self, job_id: str) -> list[DiffSnapshot]:
        return list(self._snapshots.get(job_id, []))

    def has_snapshot(self, job_id: str) -> bool:
        return job_id in self._snapshots and len(self._snapshots[job_id]) > 0

    def clear_snapshots(self, job_id: str | None = None) -> None:
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
        snapshots = self.get_snapshots(job_id)

        if not snapshots:
            logger.warning("No snapshots found for job %s, creating empty rollback plan", job_id)
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

        logger.info("Created rollback plan: %s", plan.summary)
        return plan

    def detect_cascade_dependencies(
        self,
        job_id: str,
        applied_history: list[Any] | None = None,
    ) -> list[str]:
        target_snaps = self.get_snapshots(job_id)
        target_files = {s.file_path for s in target_snaps}
        return detect_dependent_jobs(
            job_id=job_id,
            target_files=target_files,
            applied_history=applied_history,
        )

    # ── 回滚执行 API ───────────────────────────────

    def execute_rollback(
        self,
        plan: RollbackPlan,
        verification_commands: list[str] | None = None,
    ) -> RollbackResult:
        start_time = time.monotonic()

        if not plan.snapshots:
            logger.warning("Empty rollback plan for job %s, skipping", plan.job_id)
            return RollbackResult(
                status=RollbackStatus.SKIPPED,
                plan=plan,
                recommendation="无快照可用，建议使用 Git 回滚：git checkout -- . 或 git reset --hard HEAD~1",
            )

        restored, failed = restore_from_snapshots(
            workspace_root=self.workspace_root,
            snapshots=plan.snapshots,
        )
        status = compute_rollback_status(restored, failed)
        elapsed = time.monotonic() - start_time

        verification_passed: bool | None = None
        verification_output = ""
        if self.verify_after_rollback and verification_commands and restored:
            verification_passed, verification_output = run_post_rollback_verification(
                self.workspace_root,
                verification_commands,
            )

        recommendation = self._generate_recommendation(
            status=status,
            plan=plan,
            restored=restored,
            failed=failed,
            verification_passed=verification_passed,
        )

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

        self._rollback_history.append(result)
        logger.info("Rollback completed: %s", result.summary)
        return result

    def smart_rollback(
        self,
        job_id: str,
        reason: RollbackReason,
        reason_detail: str = "",
        verification_commands: list[str] | None = None,
        applied_history: list[Any] | None = None,
    ) -> RollbackResult:
        dependencies = []
        if applied_history:
            dependencies = self.detect_cascade_dependencies(job_id, applied_history)

        plan = self.create_rollback_plan(
            job_id=job_id,
            reason=reason,
            reason_detail=reason_detail,
            dependent_job_ids=dependencies,
        )
        return self.execute_rollback(plan, verification_commands=verification_commands)

    # ── 查询 API ──────────────────────────────────

    def get_rollback_history(self, limit: int = 20) -> list[RollbackResult]:
        return list(self._rollback_history[-limit:])

    def get_rollback_statistics(self) -> dict[str, Any]:
        return build_rollback_statistics(self._rollback_history)

    # ── 内部方法 ──────────────────────────────────

    @staticmethod
    def _generate_recommendation(
        status: RollbackStatus,
        plan: RollbackPlan,
        restored: list[str],
        failed: list[str],
        verification_passed: bool | None,
    ) -> str:
        _ = restored  # keep signature backward-compatible
        return build_rollback_recommendation(
            status=status,
            plan=plan,
            failed=failed,
            verification_passed=verification_passed,
        )


__all__ = [
    "RollbackReason",
    "RollbackStatus",
    "DiffSnapshot",
    "RollbackPlan",
    "RollbackResult",
    "RollbackRecovery",
]

