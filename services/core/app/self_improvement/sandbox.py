"""
安全沙箱执行环境 — 自编程能力的 Phase 4 核心之一

在应用补丁到真实工作区之前，先在隔离环境中：
1. 复制受影响文件到临时目录
2. 在临时副本上应用补丁
3. 运行验证命令（测试套件）
4. 检查结果，决定是否应用到真实工作区

安全特性：
- 超时控制（防止无限运行）
- 资源限制（可配置最大内存/输出）
- 临时目录自动清理
- 不修改任何真实文件
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# ── 数据模型 ────────────────────────────────────────────


@dataclass(frozen=True)
class SandboxResult:
    """沙箱执行结果。"""

    success: bool = False
    exit_code: int = -1
    stdout: str = ""
    stderr: str = ""
    duration_seconds: float = 0.0
    timed_out: bool = False
    error_message: str | None = None  # 非零退出或异常时的描述

    @property
    def summary(self) -> str:
        """人类可读的结果摘要。"""
        if self.timed_out:
            return f"⏰ 超时 ({self.duration_seconds:.1f}s)"
        if not self.success:
            return f"❌ 失败 (exit={self.exit_code}): {self.error_message or self.stderr[:200]}"
        return f"✅ 通过 ({self.duration_seconds:.1f}s, {len(self.stdout)}B output)"


@dataclass(frozen=True)
class SandboxConfig:
    """沙箱配置。"""

    timeout_seconds: float = 30.0          # 单个命令最大执行时间
    max_output_bytes: int = 2 * 1024 * 1024  # 最大输出大小 (2MB)
    cleanup_on_exit: bool = True             # 退出时清理临时目录
    env_vars: dict[str, str] = field(default_factory=dict)  # 额外环境变量


# ── 主类 ────────────────────────────────────────────────


class SandboxEnvironment:
    """安全沙箱——在隔离的临时目录中预验证补丁。

    工作流程::

        sandbox = SandboxEnvironment(workspace_root, config)
        result = sandbox.prevalidate(job)

        if result.success:
            # 安全！可以 apply 到真实工作区
            executor.apply(job)
        else:
            # 补丁有问题，不应用
            logger.warning(f"沙箱预验证失败: {result.summary}")
    """

    DEFAULT_CONFIG = SandboxConfig()

    def __init__(
        self,
        workspace_root: Path,
        config: SandboxConfig | None = None,
    ) -> None:
        """
        Args:
            workspace_root: 项目根目录（用于复制源文件）
            config: 沙箱配置参数
        """
        self.workspace_root = workspace_root
        self.config = config or self.DEFAULT_CONFIG
        self._temp_dir: Path | None = None

    # ── 公共 API ────────────────────────────────────

    def prevalidate(
        self,
        edits: list[Any],
        verification_commands: list[str],
        job_id: str = "",
    ) -> SandboxResult:
        """在沙箱中预验证补丁。

        1. 创建临时目录并复制相关文件
        2. 应用补丁到临时副本
        3. 运行验证命令
        4. 返回结果（不触碰真实文件）

        Args:
            edits: SelfImprovementEdit 列表
            verification_commands: 要运行的测试/验证命令列表
            job_id: 用于日志标识

        Returns:
            SandboxResult 执行结果
        """
        import time

        # 收集需要复制的文件路径集合
        files_to_copy: set[Path] = set()
        for edit in edits:
            fp = getattr(edit, 'file_path', None)
            if fp:
                p = self.workspace_root / fp
                if p.exists():
                    files_to_copy.add(p)
                    # 也复制父级 __init__.py 等包结构文件
                    for parent in p.parents:
                        init_file = parent / "__init__.py"
                        if init_file.exists() and init_file != p:
                            files_to_copy.add(init_file)
                        if parent == self.workspace_root or len(parent.relative_to(self.workspace_root).parts) > 5:
                            break

        # 如果没有需要验证的命令或没有文件，快速返回
        if not verification_commands:
            return SandboxResult(
                success=False,
                error_message="没有提供验证命令",
            )

        if not files_to_copy:
            return SandboxResult(
                success=False,
                error_message="没有找到需要复制的文件",
            )

        # 创建临时沙箱目录
        temp_dir = self._create_sandbox()
        start_time = time.monotonic()

        try:
            # 复制文件到沙箱
            copied = self._copy_files_to_sandbox(files_to_copy, temp_dir)

            # 应用补丁到沙箱中的副本
            self._apply_edits_in_sandbox(edits, temp_dir)

            # 运行验证命令
            result = self._run_commands_in_sandbox(
                verification_commands,
                temp_dir,
                start_time,
            )

            return result

        except Exception as exc:
            elapsed = time.monotonic() - start_time
            logger.error(f"Sandbox error for job {job_id}: {exc}")
            return SandboxResult(
                success=False,
                duration_seconds=elapsed,
                error_message=f"沙箱异常: {exc}",
            )
        finally:
            if self.config.cleanup_on_exit:
                self._cleanup(temp_dir)

    def quick_check_syntax(
        self,
        file_path: str,
        file_content: str | None = None,
    ) -> SandboxResult:
        """快速语法检查单个 Python 文件。

        用 `python -c "compile(...)"` 或 `python -m py_compile` 检查，
        比完整测试快得多，适合做第一道防线。

        Args:
            file_path: 文件相对路径
            file_content: 文件内容（None 则从工作区读取）

        Returns:
            语法检查结果
        """
        import time

        full_path = self.workspace_root / file_path
        content = file_content
        if content is None:
            if not full_path.exists():
                return SandboxResult(
                    success=False,
                    error_message=f"文件不存在: {file_path}",
                )
            content = full_path.read_text(encoding="utf-8")

        # 对 .py 文件做编译检查
        if file_path.endswith(".py"):
            start_time = time.monotonic()
            try:
                compile(content, file_path, "exec")
                elapsed = time.monotonic() - start_time
                return SandboxResult(success=True, duration_seconds=elapsed)
            except SyntaxError as exc:
                elapsed = time.monotonic() - start_time
                return SandboxResult(
                    success=False,
                    duration_seconds=elapsed,
                    error_message=f"语法错误: {exc.msg} (行 {exc.lineno})",
                    stderr=str(exc),
                )
            except Exception as exc:
                elapsed = time.monotonic() - start_time
                return SandboxResult(
                    success=False,
                    duration_seconds=elapsed,
                    error_message=f"编译异常: {exc}",
                )

        # 非 Python 文件，简单检查是否为空
        if not content.strip():
            return SandboxResult(
                success=False,
                error_message="文件内容为空",
            )

        return SandboxResult(success=True)

    # ── 内部方法 ────────────────────────────────────

    def _create_sandbox(self) -> Path:
        """创建临时沙箱目录。"""
        temp_dir = Path(tempfile.mkdtemp(prefix="si-sandbox-"))
        self._temp_dir = temp_dir
        logger.debug(f"Created sandbox at {temp_dir}")
        return temp_dir

    def _copy_files_to_sandbox(
        self,
        files: set[Path],
        sandbox_dir: Path,
    ) -> dict[Path, Path]:
        """将文件复制到沙箱中，保持目录结构。返回映射表。"""
        mapping: dict[Path, Path] = {}
        for src in sorted(files):
            rel = src.relative_to(self.workspace_root)
            dst = sandbox_dir / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            mapping[src] = dst
        logger.debug(f"Copied {len(files)} files to sandbox")
        return mapping

    def _apply_edits_in_sandbox(self, edits: list[Any], sandbox_dir: Path) -> None:
        """在沙箱内的副本上应用编辑操作。"""
        from app.domain.models import EditKind

        for edit in edits:
            path = sandbox_dir / edit.file_path
            kind = getattr(edit, 'kind', EditKind.REPLACE)

            if kind == EditKind.CREATE:
                if edit.file_content:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(edit.file_content, encoding="utf-8")
                continue

            if kind == EditKind.INSERT:
                original = path.read_text(encoding="utf-8") if path.exists() else ""
                if edit.insert_after and edit.insert_after in original:
                    insert_pos = original.index(edit.insert_after) + len(edit.insert_after)
                    updated = original[:insert_pos] + edit.replace_text + original[insert_pos:]
                    path.write_text(updated, encoding="utf-8")
                continue

            # REPLACE
            if path.exists():
                original = path.read_text(encoding="utf-8")
                search_key = edit.search_text or ""
                replace_val = edit.replace_text or ""
                if search_key in original:
                    updated = original.replace(search_key, replace_val, 1)
                    path.write_text(updated, encoding="utf-8")

    def _run_commands_in_sandbox(
        self,
        commands: list[str],
        sandbox_dir: Path,
        start_time: float,
    ) -> SandboxResult:
        """在沙箱目录中依次运行验证命令。"""
        all_stdout: list[str] = []
        all_stderr: list[str] = []
        last_code = -1

        env = {
            **os.environ,
            "PYTHONDONTWRITEBYTECODE": "1",
            **self.config.env_vars,
        }

        for cmd in commands:
            try:
                result = subprocess.run(
                    cmd,
                    shell=True,
                    cwd=sandbox_dir,
                    capture_output=True,
                    text=True,
                    timeout=self.config.timeout_seconds,
                    env=env,
                )
                last_code = result.returncode

                stdout_part = (result.stdout or "").strip()
                stderr_part = (result.stderr or "").strip()

                # 截断过大的输出
                if len(stdout_part) > self.config.max_output_bytes:
                    stdout_part = stdout_part[:self.config.max_output_bytes] + "\n... [truncated]"
                if len(stderr_part) > self.config.max_output_bytes:
                    stderr_part = stderr_part[:self.config.max_output_bytes] + "\n... [truncated]"

                all_stdout.append(f"$ {cmd}\n{stdout_part}" if stdout_part else f"$ {cmd}")
                all_stderr.append(stderr_part)

                if last_code != 0:
                    break

            except subprocess.TimeoutExpired:
                elapsed = __import__("time").monotonic() - start_time
                return SandboxResult(
                    success=False,
                    exit_code=-1,
                    stdout="\n".join(all_stdout),
                    stderr="\n".join(all_stderr),
                    duration_seconds=elapsed,
                    timed_out=True,
                    error_message=(
                        f"命令超时 ({self.config.timeout_seconds}s): {cmd}"
                    ),
                )
            except Exception as exc:
                elapsed = __import__("time").monotonic() - start_time
                return SandboxResult(
                    success=False,
                    exit_code=-1,
                    stdout="\n".join(all_stdout),
                    stderr="\n".join(all_stderr),
                    duration_seconds=elapsed,
                    error_message=f"命令执行异常: {cmd} → {exc}",
                )

        import time
        elapsed = time.monotonic() - start_time
        passed = last_code == 0 and len(commands) > 0

        return SandboxResult(
            success=passed,
            exit_code=last_code,
            stdout="\n".join(all_stdout),
            stderr="\n".join(all_stderr),
            duration_seconds=elapsed,
            error_message=None if passed else (all_stderr[-1] if all_stderr else f"exit code {last_code}"),
        )

    def _cleanup(self, sandbox_dir: Path) -> None:
        """清理临时目录。"""
        try:
            if sandbox_dir.exists():
                shutil.rmtree(sandbox_dir, ignore_errors=True)
                logger.debug(f"Cleaned up sandbox {sandbox_dir}")
        except Exception as exc:
            logger.warning(f"Failed to cleanup sandbox {sandbox_dir}: {exc}")
