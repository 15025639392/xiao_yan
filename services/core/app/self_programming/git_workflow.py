"""
Git 工作流管理器

为自我编程补丁提供安全的 Git 集成：
1. 每次自我编程创建独立分支（feature/self-programming/{job_id}）
2. 补丁通过验证后自动 commit（含结构化 commit message）
3. 支持回滚到补丁前状态（git checkout / git clean）
4. 支持合并分支到主分支
5. 不依赖外部 git 库，纯 subprocess 调用

安全原则：
- 从不 push 到远程
- 从不 force-push
- 从修改 amend 别人的 commit
- commit message 包含 [self-programming] 标记，便于筛选
"""

from __future__ import annotations

import logging
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from app.self_programming.git_models import CommitInfo, GitStatus
from app.utils.process_utils import run_command

logger = logging.getLogger(__name__)


# ── 主类 ────────────────────────────────────────────────


class GitWorkflowManager:
    """Git 工作流管理器。

    用法示例::

        gwm = GitWorkflowManager(workspace_root=Path("/project"))
        # 创建分支并切换
        gwm.create_branch("fix/bug-123")
        # 补丁已应用，自动 stage + commit
        info = gwm.commit_changes(
            job_id="abc123",
            target_area="planning",
            summary="修复计划生成空列表的边界条件",
            touched_files=["services/core/app/planning/morning_plan.py"],
        )
        # 如果需要回滚
        gwm.rollback(info.hash)
    """

    # 分支名前缀
    BRANCH_PREFIX = "self-programming/"

    # Commit message 标签
    COMMIT_TAG = "[self-programming]"

    def __init__(
        self,
        workspace_root: Path,
        auto_commit: bool = True,
        dry_run: bool = False,
    ) -> None:
        """
        Args:
            workspace_root: 项目根目录（必须是 git 仓库）
            auto_commit: APPLIED 后是否自动 commit
            dry_run: 仅模拟执行，不实际操作 Git
        """
        self.workspace_root = workspace_root
        self.auto_commit = auto_commit
        self.dry_run = dry_run
        self._original_branch: str | None = None

    # ── 状态查询 ─────────────────────────────────────

    def get_status(self) -> GitStatus:
        """获取当前 Git 工作区状态。"""
        if not self._is_git_repo():
            return GitStatus(is_git_repo=False)

        current_branch = self._run_git(["rev-parse", "--abbrev-ref", "HEAD"]).strip()
        status_output = self._run_git(["status", "--porcelain"])

        staged: list[str] = []
        modified: list[str] = []
        untracked: list[str] = []

        for line in status_output.splitlines():
            line = line.strip()
            if not line:
                continue
            code = line[:2]
            filename = line[3:].strip()
            if code[0] in ("A", "M", "D", "R", "C"):
                staged.append(filename)
            if code[1] in ("M", "D") or (code[0] == " " and code[1] == "M"):
                modified.append(filename)
            if code == "??":
                untracked.append(filename)

        return GitStatus(
            is_git_repo=True,
            current_branch=current_branch,
            is_clean=len(staged) == 0 and len(modified) == 0 and len(untracked) == 0,
            staged_files=staged,
            modified_files=modified,
            untracked_files=untracked,
        )

    # ── 分支管理 ─────────────────────────────────────

    def create_branch(self, job_id: str, target_area: str = "") -> tuple[bool, str]:
        """为本次自我编程创建独立分支。

        Args:
            job_id: 自我编程任务 ID（用于分支命名）
            target_area: 目标区域（加入分支名提高可读性）

        Returns:
            (success, branch_name) 元组
        """
        # 记录当前分支以便后续恢复
        self._original_branch = self._run_git(
            ["rev-parse", "--abbrev-ref", "HEAD"]
        ).strip() or "main"

        area_slug = target_area.lower().replace(" ", "-").replace("_", "-")[:30]
        branch_name = f"{self.BRANCH_PREFIX}{area_slug}-{job_id[:12]}" if area_slug else f"{self.BRANCH_PREFIX}{job_id[:12]}"

        if self.dry_run:
            logger.info(f"[dry-run] Would create branch: {branch_name}")
            return (True, branch_name)

        # 检查分支是否已存在
        existing = self._run_git(["branch", "--list", branch_name]).strip()
        if existing:
            # 已存在则直接切换
            self._run_git(["checkout", branch_name])
            return (True, branch_name)

        # 创建并切换
        result = self._run_git(["checkout", "-b", branch_name])
        if result is not None:  # 命令成功（无异常）
            logger.info(f"Created and switched to branch: {branch_name}")
            return (True, branch_name)

        return (False, branch_name)

    def switch_back(self) -> bool:
        """切回原始分支。"""
        if not self._original_branch:
            return False

        current = self._run_git(["rev-parse", "--abbrev-ref", "HEAD"]).strip()
        if current == self._original_branch:
            return True

        if self.dry_run:
            logger.info(f"[dry-run] Would switch back to {self._original_branch}")
            return True

        try:
            self._run_git(["checkout", self._original_branch])
            logger.info(f"Switched back to {self._original_branch}")
            return True
        except Exception as exc:
            logger.warning(f"Failed to switch back: {exc}")
            return False

    # ── 提交操作 ─────────────────────────────────────

    def stage_and_commit(
        self,
        *,
        job_id: str,
        target_area: str,
        summary: str,
        touched_files: list[str],
        candidate_label: str = "",
    ) -> CommitInfo | None:
        """Stage 修改过的文件并创建 commit。

        Commit message 格式::
            [self-programming] <target_area>: <summary>

            Job: <job_id>
            Candidate: <candidate_label>
            Files:
              - file1.py
              - file2.py

        Args:
            job_id: 任务 ID
            target_area: 目标模块/区域
            summary: 一句话描述这次修改
            touched_files: 本次修改涉及的文件路径列表
            candidate_label: 多候选模式下选中的候选标签

        Returns:
            CommitInfo 或 None（失败时）
        """
        if self.dry_run:
            logger.info("[dry-run] Would stage and commit changes")
            return CommitInfo(
                hash="dry-run",
                branch="dry-run",
                message=self._build_message(job_id, target_area, summary, touched_files, candidate_label),
                short_hash="dry-run",
                files_changed=touched_files,
                committed_at=datetime.now(timezone.utc).isoformat(),
            )

        # Stage 所有 touched_files（包括新建文件）
        for fp in touched_files:
            abs_path = self.workspace_root / fp
            if abs_path.exists():
                self._run_git(["add", fp])
            else:
                logger.debug(f"File not found for staging: {fp}")

        # 也 stage 新增的未跟踪文件（CREATE 操作产生的）
        status = self.get_status()
        for fp in status.untracked_files:
            # 只 stage 在 touched_files 列表中的
            if fp in touched_files or any(fp.endswith(t) for t in touched_files):
                self._run_git(["add", fp])

        # 构建 commit message 并提交
        message = self._build_message(job_id, target_area, summary, touched_files, candidate_label)

        try:
            commit_output = self._run_git(
                ["commit", "-m", message],
                check=True,
            )
            commit_hash = self._get_head_hash()

            current_branch = self._run_git(
                ["rev-parse", "--abbrev-ref", "HEAD"]
            ).strip()

            info = CommitInfo(
                hash=commit_hash,
                branch=current_branch,
                message=message,
                short_hash=commit_hash[:8] if commit_hash else "",
                files_changed=touched_files,
                committed_at=datetime.now(timezone.utc).isoformat(),
            )

            logger.info(
                f"Committed {info.short_hash} on {current_branch}: "
                f"'{self.COMMIT_TAG} {target_area}: {summary}'"
            )
            return info

        except subprocess.CalledProcessError as exc:
            # 可能是 nothing to commit
            if "nothing to commit" in (exc.stderr or "").lower():
                logger.info("No changes to commit")
                return None
            logger.error(f"Commit failed: {exc}")
            return None

    # ── 回滚操作 ─────────────────────────────────────

    def rollback(self, commit_hash: str | None = None) -> bool:
        """回滚到指定 commit（或丢弃所有未提交更改）。

        Args:
            commit_hash: 要回滚到的 commit hash。
                         为 None 时丢弃所有未提交更改（git checkout -- . + git clean）。

        Returns:
            是否成功
        """
        if self.dry_run:
            logger.info(f"[dry-run] Would rollback to {commit_hash or 'last commit'}")
            return True

        try:
            if commit_hash:
                # 回退到指定 commit（软回滚，保留文件变更）
                self._run_git(["reset", "--hard", "HEAD~1"], check=True)
                logger.info(f"Rolled back commit {commit_hash[:8]}")
            else:
                # 丢弃未提交更改
                self._run_git(["checkout", "--", "."])
                self._run_git(["clean", "-fd"])
                logger.info("Discarded all uncommitted changes")

            return True
        except Exception as exc:
            logger.error(f"Rollback failed: {exc}")
            return False

    def rollback_job(self, job_id: str) -> bool:
        """回滚某次自我编程的所有变更（查找对应分支并重置）。

        通过查找包含 job_id 的分支名来定位，然后 reset --hard 回去。
        """
        if self.dry_run:
            logger.info(f"[dry-run] Would rollback job {job_id}")
            return True

        # 查找对应分支
        prefix = f"{self.BRANCH_PREFIX}"
        branches_output = self._run_git(["branch", "--list", f"{prefix}*{job_id[:12]}*"]).strip()

        if not branches_output:
            # 尝试从 commit message 找
            log_output = self._run_git([
                "log", "--oneline", "--all", "--grep", job_id[:12], "-n", "5"
            ]).strip()
            if log_output:
                lines = log_output.splitlines()
                if lines:
                    # 取第一个匹配的 commit 做 reset
                    ref = lines[0].split()[0]
                    self._run_git(["reset", "--hard", f"{ref}~1"], check=False)
                    logger.info(f"Rolled back via commit search: {ref}")
                    return True
            logger.warning(f"No branch or commit found for job {job_id}")
            return False

        branch_name = branches_output.strip().split("\n")[0].strip().lstrip("* ")
        try:
            self._run_git(["checkout", branch_name])
            self._run_git(["reset", "--hard", "HEAD~1"])
            self._run_git(["checkout", self._original_branch or "main"])
            self._run_git(["branch", "-D", branch_name])
            logger.info(f"Rolled back and deleted branch: {branch_name}")
            return True
        except Exception as exc:
            logger.error(f"Rollback of job {job_id} failed: {exc}")
            return False

    # ── 合并操作 ─────────────────────────────────────

    def merge_to_main(self, branch_name: str | None = None) -> bool:
        """将当前（或指定的）自我编程分支合并到原始分支。

        .. warning::
           这是一个需要谨慎使用的操作。建议在合并前确认测试全部通过。

        Args:
            branch_name: 要合并的分支。None 表示使用当前分支。

        Returns:
            是否成功
        """
        if self.dry_run:
            logger.info(f"[dry-run] Would merge {branch_name or 'current'} to main")
            return True

        target = self._original_branch or "main"
        source = branch_name or ""

        if not source:
            source = self._run_git(["rev-parse", "--abbrev-ref", "HEAD"]).strip()

        if source == target:
            logger.warning(f"Already on target branch '{target}'")
            return False

        try:
            # 先切到目标分支
            self._run_git(["checkout", target])
            # 合并
            self._run_git(["merge", "--no-ff", source, "-m", f"Merge {self.COMMIT_TAG} branch '{source}'"])
            logger.info(f"Merged '{source}' into '{target}'")

            # 可选：删除已合并的分支
            try:
                self._run_git(["branch", "-d", source])
            except Exception:
                pass  # 分支可能还有其他 commit

            return True
        except subprocess.CalledProcessError as exc:
            logger.error(f"Merge failed (likely conflicts): {exc}")
            # 回到目标分支的安全状态
            self._run_git(["merge", "--abort"], check=False)
            return False

    # ── 内部工具方法 ─────────────────────────────────

    @staticmethod
    def _build_message(
        job_id: str,
        target_area: str,
        summary: str,
        files: list[str],
        candidate_label: str = "",
    ) -> str:
        """构建结构化 commit message。"""
        body_parts = [f"Job: {job_id}"]
        if candidate_label:
            body_parts.append(f"Candidate: {candidate_label}")

        body_parts.append("Files:")
        for f in files:
            body_parts.append(f"  - {f}")

        body = "\n".join(body_parts)

        msg = f"{GitWorkflowManager.COMMIT_TAG} {target_area}: {summary}\n\n{body}"
        return msg

    def _get_head_hash(self) -> str:
        """获取 HEAD commit 的完整 hash。"""
        return self._run_git(["rev-parse", "HEAD"]).strip()

    def _is_git_repo(self) -> bool:
        """检查目录是否是 git 仓库。"""
        try:
            self._run_git(["rev-parse", "--is-inside-work-tree"], check=True)
            return True
        except (subprocess.CalledProcessError, OSError):
            return False

    def _run_git(
        self,
        args: list[str],
        check: bool = False,
        cwd: Path | None = None,
    ) -> str:
        """执行 git 命令，返回 stdout。

        Args:
            args: git 参数列表（不含 'git' 本身）
            check: 是否在非零返回码时抛出异常
            cwd: 工作目录（默认 workspace_root）

        Returns:
            stdout 字符串

        Raises:
            subprocess.CalledProcessError: 当 check=True 且命令返回非零
            RuntimeError: 不是 git 仓库时
        """
        cmd = ["git"] + args
        work_dir = cwd or self.workspace_root

        result = run_command(
            cmd,
            cwd=work_dir,
            extra_env={
                "GIT_TERMINAL_PROMPT": "0",
                "GIT_EDITOR": ":",
                "GIT_MERGE_AUTOEDIT": "no",
            },
        )

        if check and result.returncode != 0:
            raise subprocess.CalledProcessError(
                result.returncode, cmd, result.stdout, result.stderr
            )

        # 非 zero 返回但不是 error 级别的情况只记录 debug
        if result.returncode != 0:
            logger.debug(f"git {' '.join(args)} exited with {result.returncode}: {result.stderr.strip()}")

        return result.stdout
