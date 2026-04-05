"""Command Runner — 安全命令执行器。"""

from __future__ import annotations

import logging
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.tools.models import ToolExecutionResult
from app.tools.sandbox import (
    CommandSandbox,
    SandboxViolation,
    ToolMetadata,
    ToolSafetyLevel,
)

logger = logging.getLogger(__name__)


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
            "tool_name": self.result.tool_name,
            "safety_level": self.result.safety_level,
            "created_at": self.created_at,
        }
        if self.result.error:
            d["error"] = self.result.error
        return d


# ── 主类 ────────────────────────────────────────────────


class CommandRunner:
    """命令执行器。"""

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

    def run(self, command: str) -> ToolExecutionResult:
        """执行命令并返回结构化 ToolExecutionResult。

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
                error=str(exc),
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
            tool_name=tool_meta.name if tool_meta else None,
            safety_level=tool_meta.safety_level.value if tool_meta else None,
            working_directory=cwd_str or str(Path.cwd()),
            error=error_msg,
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
