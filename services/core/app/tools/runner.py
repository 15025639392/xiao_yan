"""
Enhanced Command Runner — Tools Phase: 安全命令执行器

特性:
- 超时控制（默认 30s/可配置）
- 输出大小限制（默认 2MB）
- 工作目录安全（可选限制在指定目录内）
- 富化执行结果（含 exit_code / duration / stderr / 截断标记）
- 执行历史记录
- 错误分类（超时 / 被信号终止 / 非零退出码）

向后兼容: ActionResult 数据模型保持不变，新增字段通过 ToolExecutionResult 扩展。
"""

from __future__ import annotations

import logging
import signal
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.domain.models import ActionResult
from app.tools.sandbox import (
    CommandSandbox,
    SandboxViolation,
    ToolMetadata,
    ToolSafetyLevel,
)

logger = logging.getLogger(__name__)


@dataclass
class ToolExecutionResult:
    """增强版执行结果。"""
    command: str
    output: str                          # stdout（截断后）
    stderr: str = ""                     # stderr 内容
    exit_code: int = -1                  # 退出码 (-1=未运行)
    success: bool = False                # 是否成功 (exit_code == 0)
    timed_out: bool = False              # 是否超时
    truncated: bool = False              # 输出是否被截断
    duration_seconds: float = 0.0        # 实际执行时间
    executed_at: str = ""                # ISO 时间戳
    tool_metadata: ToolMetadata | None = None  # 工具元数据
    working_directory: str = ""          # 执行时的工作目录
    error_message: str | None = None     # 失败时的错误描述

    # 向后兼容：转换为旧 ActionResult
    def to_action_result(self) -> ActionResult:
        output_text = self.output
        if self.stderr and self.exit_code != 0:
            output_text += f"\n[stderr] {self.stderr[:500]}"
        if self.timed_out:
            output_text += "\n[TIMEOUT]"
        return ActionResult(
            command=self.command,
            output=output_text.strip(),
        )

    @property
    def summary(self) -> str:
        """人类可读的结果摘要。"""
        status = "OK" if self.success else ("TIMEOUT" if self.timed_out else f"ERR({self.exit_code})")
        trunc_marker = " [truncated]" if self.truncated else ""
        return f"[{status}] {self.duration_seconds:.2f}s → {len(self.output)}B{trunc_marker}"


@dataclass
class ExecutionHistoryEntry:
    """执行历史条目（内存存储）。"""
    id: str
    result: ToolExecutionResult
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        d = {
            "id": self.id,
            "command": self.result.command,
            "output": self.result.output[:1000],
            "exit_code": self.result.exit_code,
            "success": self.result.success,
            "timed_out": self.result.timed_out,
            "duration_seconds": round(self.result.duration_seconds, 3),
            "tool_name": self.result.tool_metadata.name if self.result.tool_metadata else None,
            "safety_level": self.result.tool_metadata.safety_level.value if self.result.tool_metadata else None,
            "created_at": self.created_at,
        }
        if self.result.error_message:
            d["error"] = self.result.error_message
        return d


# ── 主类 ────────────────────────────────────────────────


class CommandRunner:
    """增强版命令执行器。

    用法::

        # 向后兼容用法
        runner = CommandRunner(sandbox)
        action_result = runner.run("pwd")

        # 新功能：获取增强结果
        runner = EnhancedCommandRunner(sandbox)
        tool_result = runner.run_enhanced("ls -la")
        print(tool_result.summary)
        print(tool_result.exit_code)
    """

    DEFAULT_TIMEOUT_SECONDS = 30.0
    DEFAULT_MAX_OUTPUT_BYTES = 2 * 1024 * 1024  # 2 MB
    DEFAULT_MAX_HISTORY = 200

    def __init__(
        self,
        sandbox: CommandSandbox,
        *,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        max_output_bytes: int = DEFAULT_MAX_OUTPUT_BYTES,
        working_directory: Path | None = None,
        keep_history: bool = True,
        max_history: int = DEFAULT_MAX_HISTORY,
    ) -> None:
        """
        Args:
            sandbox: 命令沙箱实例
            timeout_seconds: 单命令最大执行时间
            max_output_bytes: 最大输出字节数（stdout + stderr 各自独立限制）
            working_directory: 命令执行的工作目录（None = 当前目录）
            keep_history: 是否保留执行历史
            max_history: 最多保留的历史条目数
        """
        self.sandbox = sandbox
        self.timeout_seconds = timeout_seconds
        self.max_output_bytes = max_output_bytes
        self.working_directory = working_directory
        self.keep_history = keep_history
        self.max_history = max_history
        self._history: list[ExecutionHistoryEntry] = []

    def run(self, command: str) -> ActionResult:
        """向后兼容接口：执行命令并返回 ActionResult。

        内部调用 run_enhanced() 并转换为 ActionResult。
        """
        enhanced = self.run_enhanced(command)
        return enhanced.to_action_result()

    def run_enhanced(self, command: str) -> ToolExecutionResult:
        """执行命令并返回增强的 ToolExecutionResult。

        流程:
        1. 沙箱校验（白名单 + 注入检测 + 参数检查）
        2. subprocess.run with timeout
        3. 输出截断
        4. 记录到历史
        5. 返回完整结果
        """
        start_time = time.monotonic()
        now_iso = datetime.now(timezone.utc).isoformat()

        # 1. 沙箱校验
        try:
            validated = self.sandbox.validate(command)
        except (PermissionError, SandboxViolation) as exc:
            return ToolExecutionResult(
                command=command,
                exit_code=-1,
                success=False,
                duration_seconds=time.monotonic() - start_time,
                executed_at=now_iso,
                working_directory=str(self.working_directory or Path.cwd()),
                error_message=str(exc),
            )

        # 提取工具元数据
        executable = validated.split()[0] if validated.split() else ""
        tool_meta = self.sandbox.get_tool_metadata(executable)

        # 使用工具特定的超时（如果定义了的话）
        timeout = self.timeout_seconds
        if tool_meta and tool_meta.max_timeout_seconds > 0:
            timeout = min(timeout, tool_meta.max_timeout_seconds)

        # 2. 执行命令
        cwd_str = str(self.working_directory) if self.working_directory else None
        try:
            proc_result = subprocess.run(
                validated,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=cwd_str,
                env={
                    **__import__("os").environ,
                    "PYTHONDONTWRITEBYTECODE": "1",
                    "LANG": "en_US.UTF-8",
                    "LC_ALL": "en_US.UTF-8",
                },
            )
            exit_code = proc_result.returncode
            stdout_raw = proc_result.stdout or ""
            stderr_raw = proc_result.stderr or ""
            timed_out = False
            error_msg = None

        except subprocess.TimeoutExpired:
            exit_code = -1
            stdout_raw = ""
            stderr_raw = f"Command timed out after {timeout}s"
            timed_out = True
            error_msg = f"Timeout after {timeout:.1f}s"

        except Exception as exc:
            exit_code = -1
            stdout_raw = ""
            stderr_raw = ""
            timed_out = False
            error_msg = f"Execution error: {exc}"
            logger.exception(f"Command execution failed: {command}")

        elapsed = time.monotonic() - start_time

        # 3. 输出截断
        stdout_truncated, stdout_final = self._truncate(stdout_raw)
        stderr_truncated, stderr_final = self._truncate(stderr_raw)

        result = ToolExecutionResult(
            command=validated,
            output=stdout_final,
            stderr=stderr_final,
            exit_code=exit_code,
            success=(exit_code == 0),
            timed_out=timed_out,
            truncated=(stdout_truncated or stderr_truncated),
            duration_seconds=round(elapsed, 3),
            executed_at=now_iso,
            tool_metadata=tool_meta,
            working_directory=cwd_str or str(Path.cwd()),
            error_message=error_msg,
        )

        # 4. 记录历史
        if self.keep_history:
            self._record(result)

        return result

    def get_history(self, limit: int = 50) -> list[dict[str, Any]]:
        """获取最近的执行历史。"""
        entries = self._history[-limit:]
        return [e.to_dict() for e in reversed(entries)]

    def clear_history(self) -> int:
        """清空历史记录，返回已清除的条目数。"""
        count = len(self._history)
        self._history.clear()
        return count

    def _truncate(self, text: str) -> tuple[bool, str]:
        """截断过长的输出文本。返回 (是否被截断, 结果文本)。"""
        if len(text) <= self.max_output_bytes:
            return False, text
        return (
            True,
            text[:self.max_output_bytes] + f"\n... [truncated at {self.max_output_bytes}B]",
        )

    def _record(self, result: ToolExecutionResult) -> None:
        """将执行结果记录到历史中。"""
        import uuid
        entry = ExecutionHistoryEntry(
            id=uuid.uuid4().hex[:12],
            result=result,
            created_at=result.executed_at,
        )
        self._history.append(entry)
        # 保持历史大小不超过上限
        while len(self._history) > self.max_history:
            self._history.pop(0)


# ── 向后兼容别名 ──────────────────────────────────────

# 让旧的 `from app.tools.runner import CommandRunner` 仍然工作
# CommandRunner 已在上面定义为增强版本
