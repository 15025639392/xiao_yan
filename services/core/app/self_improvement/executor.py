import logging
import os
import subprocess
from pathlib import Path
from typing import Any

from app.domain.models import (
    EditKind,
    SelfImprovementJob,
    SelfImprovementStatus,
    SelfImprovementVerification,
)
from app.self_improvement.git_workflow import GitWorkflowManager
from app.self_improvement.sandbox import SandboxEnvironment, SandboxResult
from app.self_improvement.conflict_detector import ConflictDetector, ConflictReport
from app.self_improvement.rollback_recovery import (
    RollbackRecovery,
    RollbackReason,
    RollbackResult,
    RollbackStatus,
)

logger = logging.getLogger(__name__)


class SelfImprovementExecutor:
    def __init__(
        self,
        workspace_root: Path,
        git_manager: GitWorkflowManager | None = None,
        sandbox: SandboxEnvironment | None = None,
        conflict_detector: ConflictDetector | None = None,
        enable_sandbox: bool = True,
        enable_conflict_check: bool = True,
        # Phase 5: 可选的回滚恢复和健康检查
        rollback_recovery: RollbackRecovery | None = None,
        auto_snapshot: bool = True,
    ) -> None:
        self.workspace_root = workspace_root
        self._backups: dict[str, dict[Path, str]] = {}
        # Phase 3: 可选的 Git 工作流管理器（传入则自动 commit）
        self.git = git_manager or GitWorkflowManager(
            workspace_root=workspace_root,
            auto_commit=True,
        )
        # Phase 4: 安全沙箱（可选，传入或自动创建）
        self.sandbox = sandbox or (
            SandboxEnvironment(workspace_root=workspace_root) if enable_sandbox else None
        )
        # Phase 4: 冲突检测器
        self.conflict_detector = conflict_detector or (
            ConflictDetector(workspace_root=workspace_root) if enable_conflict_check else None
        )
        # 开关标志
        self.enable_sandbox = enable_sandbox and (self.sandbox is not None)
        self.enable_conflict_check = enable_conflict_check and (self.conflict_detector is not None)

        # Phase 5: 回滚恢复管理器
        self.recovery = rollback_recovery or RollbackRecovery(
            workspace_root=workspace_root,
            auto_snapshot=auto_snapshot,
        )

    def apply(self, job: SelfImprovementJob) -> SelfImprovementJob:
        if not job.test_edits and not job.edits:
            return job.model_copy(
                update={
                    "status": SelfImprovementStatus.FAILED,
                    "patch_summary": "没有可执行的补丁计划。",
                }
            )

        backups: dict[Path, str] = {}
        touched_files: list[str] = []

        # Phase 5: 在修改文件之前先创建差异快照（保存原始状态用于可能的回滚）
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
                    "status": SelfImprovementStatus.FAILED,
                    "patch_summary": f"补丁应用失败：{exc}",
                    "touched_files": [],
                }
            )

        self._backups[job.id] = backups
        result = job.model_copy(
            update={
                "status": SelfImprovementStatus.VERIFYING,
                "patch_summary": f"已修改 {', '.join(touched_files)}",
                "red_verification": red_verification,
                "touched_files": touched_files,
            }
        )
        # 标记已取快照（pre-apply 时已创建）
        result = result.model_copy(update={"snapshot_taken": True})

        return result

    def verify(self, job: SelfImprovementJob) -> SelfImprovementJob:
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
                    SelfImprovementStatus.APPLIED if passed else SelfImprovementStatus.FAILED
                ),
                "verification": verification,
            }
        )

    # ── Phase 3: Git 工作流集成 ──────────────────────

    def commit_job(self, job: SelfImprovementJob) -> SelfImprovementJob:
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
        if job.status != SelfImprovementStatus.APPLIED:
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

    # ── Phase 4: 沙箱预验证 + 冲突检测 ────────────────

    def preflight_check(
        self,
        job: SelfImprovementJob,
        recent_history: list | None = None,
    ) -> SelfImprovementJob:
        """应用前的预检：冲突检测 + 沙箱预验证。

        Args:
            job: 待检查的 Job
            recent_history: 最近的自编程历史列表（用于冲突检测）

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
                        "status": SelfImprovementStatus.FAILED,
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
            # 如果没有验证命令，跳过沙箱（向后兼容旧测试）
            if not verification_cmds:
                logger.debug(f"Skipping sandbox for {job.id}: no verification commands")
                updates["sandbox_prechecked"] = False
            else:
                sandbox_result = self.sandbox.prevalidate(
                    edits=job.edits or [],
                    verification_commands=verification_cmds,
                    job_id=job.id,
                )

                updates["sandbox_prechecked"] = True
                updates["sandbox_result"] = sandbox_result.summary

                # 如果沙箱因为"没有找到文件"或环境问题而失败，降级为警告而非阻塞
                # 这允许旧测试在没有完整项目结构的情况下继续工作
                if not sandbox_result.success and not sandbox_result.timed_out:
                    error_msg = sandbox_result.error_message or ""
                    is_skipable_error = (
                        "没有找到需要复制的文件" in error_msg
                        or "file or directory not found" in (sandbox_result.stderr or "").lower()
                        or "No such file" in (sandbox_result.stderr or "")
                    )
                    if is_skipable_error:
                        logger.warning(
                            f"Sandbox pre-validation skipped for {job.id}: "
                            f"{error_msg[:100] if error_msg else sandbox_result.stderr[:100]}"
                        )
                        # 不标记 FAILED，允许继续到 apply 阶段
                        updates["sandbox_result"] = "⚠️ 跳过（沙箱环境不完整）"
                    else:
                        # 真正的测试失败 → 阻止应用
                        return job.model_copy(
                            update={
                                **updates,
                                "status": SelfImprovementStatus.FAILED,
                                "patch_summary": (
                                    f"🧪 沙箱预验证失败: {sandbox_result.summary}\n"
                                    f"{sandbox_result.stderr[:300] if sandbox_result.stderr else ''}"
                                ),
                            }
                        )
                    
                    logger.info(
                        f"Sandbox prevalidation passed for {job.id}: {sandbox_result.summary}"
                    )

        return job.model_copy(update=updates) if updates else job

    def record_successful_apply(self, job: SelfImprovementJob) -> None:
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
        for edit in edits:
            path = self.workspace_root / edit.file_path

            # CREATE kind: write new file
            if getattr(edit, 'kind', EditKind.REPLACE) == EditKind.CREATE:
                if not edit.file_content:
                    raise ValueError(f"CREATE edit missing file_content for {edit.file_path}")
                path.parent.mkdir(parents=True, exist_ok=True)
                original = ""
                if path.exists():
                    original = path.read_text(encoding="utf-8")
                backups.setdefault(path, original)
                path.write_text(edit.file_content, encoding="utf-8")
                if edit.file_path not in touched_files:
                    touched_files.append(edit.file_path)
                continue

            # INSERT kind: insert after anchor text
            if getattr(edit, 'kind', EditKind.REPLACE) == EditKind.INSERT:
                original = path.read_text(encoding="utf-8")
                if not edit.insert_after or edit.insert_after not in original:
                    raise ValueError(f"insert_after anchor not found in {edit.file_path}")
                backups.setdefault(path, original)
                insert_pos = original.index(edit.insert_after) + len(edit.insert_after)
                updated = original[:insert_pos] + edit.replace_text + original[insert_pos:]
                path.write_text(updated, encoding="utf-8")
                if edit.file_path not in touched_files:
                    touched_files.append(edit.file_path)
                continue

            # REPLACE kind (original behavior, backward compatible with old data)
            original = path.read_text(encoding="utf-8")
            search_key = edit.search_text or ""
            replace_val = edit.replace_text or ""
            if search_key not in original:
                raise ValueError(f"search text not found in {edit.file_path}")
            updated = original.replace(search_key, replace_val, 1)
            backups.setdefault(path, original)
            path.write_text(updated, encoding="utf-8")
            if edit.file_path not in touched_files:
                touched_files.append(edit.file_path)

    def _run_verification(self, commands: list[str]) -> SelfImprovementVerification:
        outputs: list[str] = []
        passed = True

        for command in commands:
            result = subprocess.run(
                command,
                shell=True,
                cwd=self.workspace_root,
                capture_output=True,
                text=True,
                env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
            )
            combined = "\n".join(
                part.strip() for part in (result.stdout, result.stderr) if part.strip()
            )
            outputs.append(f"$ {command}\n{combined}".strip())
            if result.returncode != 0:
                passed = False
                break

        summary = "\n\n".join(outputs).strip() or "没有运行验证命令。"
        return SelfImprovementVerification(
            commands=commands,
            passed=passed,
            summary=summary,
        )

    def _restore_files(self, backups: dict[Path, str]) -> None:
        for path, content in backups.items():
            if content:
                path.write_text(content, encoding="utf-8")
            elif path.exists():
                path.unlink()

    # ── Phase 2: 多候选 A/B 测试 ─────────────────────────

    def try_best(
        self,
        candidates: list,
        max_attempts: int = 3,
    ) -> SelfImprovementJob | None:
        """按评分顺序逐个尝试候选方案，返回第一个通过验证的。

        Args:
            candidates: ScoredCandidate 列表（已按 total_score 降序排列）
            max_attempts: 最大尝试次数

        Returns:
            第一个通过验证的 SelfImprovementJob，或 None（全部失败）
        """
        for idx, scored in enumerate(candidates[:max_attempts]):
            job = scored.job
            label = getattr(scored, "candidate_id", f"candidate-{idx + 1}")
            logger.info(f"Trying candidate '{label}' (score={getattr(scored, 'total_score', '?')})")

            # apply → verify 完整流程
            applied = self.apply(job)
            if applied.status == SelfImprovementStatus.FAILED:
                logger.info(f"  Candidate '{label}': apply failed — {applied.patch_summary}")
                continue

            verified = self.verify(applied)
            if verified.status == SelfImprovementStatus.APPLIED:
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

    # ── Phase 5: 回滚恢复 + 健康检查集成 ─────────────

    def smart_rollback(
        self,
        job: SelfImprovementJob,
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

    def take_snapshot(self, job: SelfImprovementJob) -> list[Any]:
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
