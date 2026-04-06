import logging
from pathlib import Path
from typing import Any

from app.domain.models import (
    SelfProgrammingJob,
    SelfProgrammingStatus,
)
from app.self_programming.git_workflow import GitWorkflowManager
from app.self_programming.sandbox import SandboxEnvironment, SandboxResult
from app.self_programming.conflict_detector import ConflictDetector, ConflictReport
from app.self_programming.executor_helpers import apply_edits, restore_files, run_verification
from app.self_programming.rollback_recovery import (
    RollbackRecovery,
    RollbackReason,
    RollbackResult,
    RollbackStatus,
)

logger = logging.getLogger(__name__)


class SelfProgrammingExecutor:
    def __init__(
        self,
        workspace_root: Path,
        git_manager: GitWorkflowManager | None = None,
        sandbox: SandboxEnvironment | None = None,
        conflict_detector: ConflictDetector | None = None,
        enable_sandbox: bool = True,
        enable_conflict_check: bool = True,
        # 可选的回滚恢复和健康检查
        rollback_recovery: RollbackRecovery | None = None,
        auto_snapshot: bool = True,
    ) -> None:
        self.workspace_root = workspace_root
        self._backups: dict[str, dict[Path, str]] = {}
        # 可选的 Git 工作流管理器（传入则自动 commit）
        self.git = git_manager or GitWorkflowManager(
            workspace_root=workspace_root,
            auto_commit=True,
        )
        # 安全沙箱（可选，传入或自动创建）
        self.sandbox = sandbox or (
            SandboxEnvironment(workspace_root=workspace_root) if enable_sandbox else None
        )
        # 冲突检测器
        self.conflict_detector = conflict_detector or (
            ConflictDetector(workspace_root=workspace_root) if enable_conflict_check else None
        )
        # 开关标志
        self.enable_sandbox = enable_sandbox and (self.sandbox is not None)
        self.enable_conflict_check = enable_conflict_check and (self.conflict_detector is not None)

        # 回滚恢复管理器
        self.recovery = rollback_recovery or RollbackRecovery(
            workspace_root=workspace_root,
            auto_snapshot=auto_snapshot,
        )

    def apply(self, job: SelfProgrammingJob) -> SelfProgrammingJob:
        if not job.test_edits and not job.edits:
            return job.model_copy(
                update={
                    "status": SelfProgrammingStatus.FAILED,
                    "patch_summary": "没有可执行的补丁计划。",
                }
            )

        backups: dict[Path, str] = {}
        touched_files: list[str] = []

        # 在修改文件之前先创建差异快照（保存原始状态用于可能的回滚）
        if self.recovery and self.recovery.auto_snapshot:
            try:
                self.recovery.snapshot_before_apply(job)
            except Exception as exc:
                logger.debug(f"Pre-apply snapshot failed (non-critical): {exc}")

        try:
            self._apply_edits(job.test_edits, backups, touched_files)
            red_verification = None
            if job.test_edits:
                red_verification = self._run_verification(
                    [] if job.verification is None else job.verification.commands
                )
                if red_verification.passed:
                    raise ValueError("红灯验证没有失败，测试没有锁住问题。")

            self._apply_edits(job.edits, backups, touched_files)
        except Exception as exc:
            self._restore_files(backups)
            return job.model_copy(
                update={
                    "status": SelfProgrammingStatus.FAILED,
                    "patch_summary": f"补丁应用失败：{exc}",
                    "touched_files": [],
                }
            )

        self._backups[job.id] = backups
        result = job.model_copy(
            update={
                "status": SelfProgrammingStatus.VERIFYING,
                "patch_summary": f"已修改 {', '.join(touched_files)}",
                "red_verification": red_verification,
                "touched_files": touched_files,
            }
        )
        # 标记已取快照（pre-apply 时已创建）
        result = result.model_copy(update={"snapshot_taken": True})

        return result

    def verify(self, job: SelfProgrammingJob) -> SelfProgrammingJob:
        verification = self._run_verification(
            [] if job.verification is None else job.verification.commands
        )
        passed = verification.passed
        if not passed:
            self._restore_job_files(job.id)

        self._backups.pop(job.id, None)
        return job.model_copy(
            update={
                "status": (
                    SelfProgrammingStatus.APPLIED if passed else SelfProgrammingStatus.FAILED
                ),
                "verification": verification,
            }
        )

    # ── Git 工作流集成 ──────────────────────

    def commit_job(self, job: SelfProgrammingJob) -> SelfProgrammingJob:
        """对已 APPLIED 的 Job 执行 Git commit。

        1. 创建独立分支（如果还没有）
        2. Stage touched_files
        3. 创建结构化 commit message
        4. 将 commit 信息写回 Job

        Args:
            job: 已通过验证 (APPLIED 状态) 的 Job

        Returns:
            附带了 Git 信息的 Job
        """
        if job.status != SelfProgrammingStatus.APPLIED:
            logger.debug(f"Skipping git commit for non-APPLIED job: {job.status}")
            return job

        # 创建分支（如果还没有）
        branch_name = job.branch_name
        if not branch_name:
            success, branch_name = self.git.create_branch(
                job_id=job.id,
                target_area=job.target_area,
            )
            if not success:
                logger.warning(f"Failed to create branch for job {job.id}")
                return job

        # 提交变更
        info = self.git.stage_and_commit(
            job_id=job.id,
            target_area=job.target_area,
            summary=job.patch_summary or job.spec[:80],
            touched_files=job.touched_files,
            candidate_label=job.candidate_label or "",
        )

        if info is not None:
            return job.model_copy(update={
                "branch_name": info.branch or branch_name,
                "commit_hash": info.hash,
                "commit_message": info.message,
            })
        else:
            # commit 可能因为 nothing to commit 返回 None
            logger.info(f"No changes to commit for job {job.id}")
            return job.model_copy(update={"branch_name": branch_name})

    # ── 沙箱预验证 + 冲突检测 ────────────────

    def preflight_check(
        self,
        job: SelfProgrammingJob,
        recent_history: list | None = None,
    ) -> SelfProgrammingJob:
        """应用前的预检：冲突检测 + 沙箱预验证。

        Args:
            job: 待检查的 Job
            recent_history: 最近的自我编程历史列表（用于冲突检测）

        Returns:
            附带了预检结果的 Job（sandbox_prechecked, conflict_severity 等字段已填充）
        """
        updates: dict = {}

        # 步骤 1: 冲突检测
        if self.enable_conflict_check and self.conflict_detector is not None:
            conflict_report = self.conflict_detector.check(
                edits=job.edits or [],
                applied_history=recent_history,
            )
            updates["conflict_severity"] = conflict_report.severity.value
            if conflict_report.conflicts:
                details = "; ".join(c.description for c in conflict_report.conflicts[:3])
                updates["conflict_details"] = details

            if conflict_report.has_blocking:
                # 阻塞级冲突，标记为失败但不修改文件
                return job.model_copy(
                    update={
                        **updates,
                        "status": SelfProgrammingStatus.FAILED,
                        "patch_summary": f"🚫 冲突检测阻止: {conflict_report.summary()}",
                        "sandbox_prechecked": False,
                    }
                )

        # 步骤 2: 沙箱预验证
        if self.enable_sandbox and self.sandbox is not None:
            verification_cmds = (
                job.verification.commands
                if job.verification else []
            )
            if not verification_cmds:
                return job.model_copy(
                    update={
                        **updates,
                        "status": SelfProgrammingStatus.FAILED,
                        "patch_summary": "🧪 缺少 verification commands，拒绝执行自我编程。",
                        "sandbox_prechecked": False,
                    }
                )
            else:
                sandbox_result = self.sandbox.prevalidate(
                    edits=job.edits or [],
                    verification_commands=verification_cmds,
                    job_id=job.id,
                )

                updates["sandbox_prechecked"] = True
                updates["sandbox_result"] = sandbox_result.summary

                if not sandbox_result.success and not sandbox_result.timed_out:
                    return job.model_copy(
                        update={
                            **updates,
                            "status": SelfProgrammingStatus.FAILED,
                            "patch_summary": (
                                f"🧪 沙箱预验证失败: {sandbox_result.summary}\n"
                                f"{sandbox_result.stderr[:300] if sandbox_result.stderr else ''}"
                            ),
                        }
                    )

        return job.model_copy(update=updates) if updates else job

    def record_successful_apply(self, job: SelfProgrammingJob) -> None:
        """记录一次成功的 apply，用于后续的循环自改检测。"""
        if self.enable_conflict_check and self.conflict_detector is not None:
            self.conflict_detector.record_apply(job.touched_files)

    def _restore_job_files(self, job_id: str) -> None:
        backups = self._backups.get(job_id, {})
        self._restore_files(backups)

    def _apply_edits(
        self,
        edits,
        backups: dict[Path, str],
        touched_files: list[str],
    ) -> None:
        apply_edits(
            workspace_root=self.workspace_root,
            edits=edits,
            backups=backups,
            touched_files=touched_files,
        )

    def _run_verification(self, commands: list[str]):
        return run_verification(self.workspace_root, commands)

    def _restore_files(self, backups: dict[Path, str]) -> None:
        restore_files(backups)

    # ── 多候选 A/B 测试 ─────────────────────────

    def try_best(
        self,
        candidates: list,
        max_attempts: int = 3,
    ) -> SelfProgrammingJob | None:
        """按评分顺序逐个尝试候选方案，返回第一个通过验证的。

        Args:
            candidates: ScoredCandidate 列表（已按 total_score 降序排列）
            max_attempts: 最大尝试次数

        Returns:
            第一个通过验证的 SelfProgrammingJob，或 None（全部失败）
        """
        for idx, scored in enumerate(candidates[:max_attempts]):
            job = scored.job
            label = getattr(scored, "candidate_id", f"candidate-{idx + 1}")
            logger.info(f"Trying candidate '{label}' (score={getattr(scored, 'total_score', '?')})")

            # apply → verify 完整流程
            applied = self.apply(job)
            if applied.status == SelfProgrammingStatus.FAILED:
                logger.info(f"  Candidate '{label}': apply failed — {applied.patch_summary}")
                continue

            verified = self.verify(applied)
            if verified.status == SelfProgrammingStatus.APPLIED:
                # 把评分信息 + candidate_label 附加到 patch_summary
                summary = verified.patch_summary or ""
                score_info = f"[selected={label}, score={getattr(scored, 'total_score', '?'):.2f}]"
                return verified.model_copy(
                    update={
                        "patch_summary": f"{score_info} {summary}".strip(),
                        "candidate_label": label,
                    }
                )

            logger.info(f"  Candidate '{label}': verify failed, rolling back")
            # verify 失败时已经自动 rollback 了

        logger.warning(f"All {min(max_attempts, len(candidates))} candidates failed verification")
        return None

    # ── 回滚恢复 + 健康检查集成 ─────────────

    def smart_rollback(
        self,
        job: SelfProgrammingJob,
        reason: RollbackReason = RollbackReason.VERIFICATION_FAILED,
        reason_detail: str = "",
    ) -> RollbackResult | None:
        """智能回滚 — 使用快照精确还原文件。

        Args:
            job: 需要回滚的 Job
            reason: 回滚原因
            reason_detail: 详细说明

        Returns:
            回滚结果，或 None（如果无快照可用）
        """
        if self.recovery is None:
            logger.warning("No rollback recovery manager available")
            return None

        verification_cmds = []
        if job.verification and job.verification.commands:
            verification_cmds = job.verification.commands

        result = self.recovery.smart_rollback(
            job_id=job.id,
            reason=reason,
            reason_detail=reason_detail,
            verification_commands=verification_cmds,
        )

        if result.status in (RollbackStatus.SUCCESS, RollbackStatus.PARTIAL):
            logger.info(f"Smart rollback completed: {result.summary}")

        return result

    def take_snapshot(self, job: SelfProgrammingJob) -> list[Any]:
        """为指定 Job 手动创建差异快照。

        通常不需要手动调用（apply 时会自动创建），
        但在某些场景下可能需要在 apply 前预取快照。

        Args:
            job: 目标 Job

        Returns:
            创建的快照列表
        """
        if self.recovery is None:
            return []

        snapshots = self.recovery.snapshot_before_apply(job)
        logger.debug(f"Manual snapshot for {job.id[:12]}: {len(snapshots)} files")
        return snapshots
