from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from app.api.browser_capability_formats import (
    format_browser_close_output,
    format_browser_extract_output,
    format_browser_snapshot_output,
    format_browser_open_output,
    merge_browser_open_with_snapshot,
)
from app.api.browser_experience_memory import (
    save_browser_experience,
    set_browser_memory_repository_getter,
)
from app.api.file_tool_helpers import file_policy_args
from app.capabilities.models import CapabilityDispatchRequest, RiskLevel
from app.capabilities.runtime import dispatch_and_wait, has_recent_capability_executor
from app.memory.repository import MemoryRepository
from app.runtime_ext.runtime_config import get_runtime_config
from app.tools.models import ToolExecutionResult
from app.tools.runner import CommandRunner
from app.tools.sandbox import SandboxViolation

DESKTOP_EXECUTOR = "desktop"
DESKTOP_EXECUTOR_MAX_AGE_SECONDS = 60


def try_dispatch_file_capability(
    capability: str,
    args: dict[str, Any],
    *,
    timeout_seconds: float = 0.8,
) -> dict[str, Any] | None:
    if not _has_recent_desktop_executor():
        return None

    result = dispatch_and_wait(
        CapabilityDispatchRequest(
            capability=capability,
            args={**args, **file_policy_args()},
            risk_level=RiskLevel.SAFE if capability in {"fs.read", "fs.list"} else RiskLevel.RESTRICTED,
            requires_approval=False,
        ),
        timeout_seconds=timeout_seconds,
        poll_interval_seconds=0.05,
    )
    if result is None:
        return None
    if not result.ok:
        if result.error_code == "not_supported":
            return None
        return {
            "error": result.error_message or result.error_code or "capability execution failed",
            "capability_request_id": result.request_id,
        }

    output = result.output if isinstance(result.output, dict) else {}
    if capability == "fs.read":
        return _format_read_output(output, args, request_id=result.request_id)
    if capability == "fs.list":
        return _format_list_output(output, args, request_id=result.request_id)
    if capability == "fs.search":
        return _format_search_output(output, args, request_id=result.request_id)
    return None


def try_dispatch_shell_capability(
    command: str,
    *,
    runner: CommandRunner,
    wait_timeout_seconds: float = 0.6,
    command_timeout_seconds: float = 60.0,
) -> ToolExecutionResult | None:
    try:
        validated = runner.sandbox.validate(command)
    except (PermissionError, SandboxViolation) as exc:
        return ToolExecutionResult(
            command=command,
            success=False,
            exit_code=-1,
            working_directory=str(runner.working_directory or Path.cwd()),
            error=str(exc),
            stderr=str(exc),
        )

    if not _has_recent_desktop_executor():
        return None

    shell_policy = get_runtime_config().get_capability_shell_policy()
    allowed_executables = shell_policy.get("allowed_executables", [])
    allowed_git_subcommands = shell_policy.get("allowed_git_subcommands", [])

    result = dispatch_and_wait(
        CapabilityDispatchRequest(
            capability="shell.run",
            args={
                "command": validated,
                "timeout_seconds": command_timeout_seconds,
                "policy_version": shell_policy.get("version"),
                "policy_revision": shell_policy.get("revision"),
                "allowed_executables": list(allowed_executables) if isinstance(allowed_executables, list) else [],
                "allowed_git_subcommands": (
                    list(allowed_git_subcommands) if isinstance(allowed_git_subcommands, list) else []
                ),
            },
            risk_level=RiskLevel.RESTRICTED,
            requires_approval=True,
        ),
        timeout_seconds=wait_timeout_seconds,
        poll_interval_seconds=0.05,
    )
    if result is None:
        return None
    if not result.ok:
        if result.error_code == "not_supported":
            return None
        return ToolExecutionResult(
            command=validated,
            success=False,
            exit_code=-1,
            working_directory=str(runner.working_directory or Path.cwd()),
            executed_at=result.audit.finished_at,
            duration_seconds=max(0.0, result.audit.duration_ms / 1000.0),
            error=result.error_message or result.error_code or "capability execution failed",
            stderr=result.error_message or "",
            tool_name="shell.run",
            safety_level="restricted",
        )

    output = result.output if isinstance(result.output, dict) else {}
    stdout = output.get("stdout", "")
    stderr = output.get("stderr", "")
    exit_code = output.get("exit_code", 0)
    success = bool(output.get("success", True))
    return ToolExecutionResult(
        command=validated,
        output=stdout if isinstance(stdout, str) else str(stdout),
        stderr=stderr if isinstance(stderr, str) else str(stderr),
        exit_code=int(exit_code) if isinstance(exit_code, int | float) else 0,
        success=success,
        timed_out=bool(output.get("timed_out", False)),
        truncated=bool(output.get("truncated", False)),
        duration_seconds=max(0.0, result.audit.duration_ms / 1000.0),
        executed_at=result.audit.finished_at,
        tool_name="shell.run",
        safety_level="restricted",
        working_directory=str(runner.working_directory or Path.cwd()),
    )


def _has_recent_desktop_executor() -> bool:
    return has_recent_capability_executor(
        DESKTOP_EXECUTOR,
        max_age_seconds=DESKTOP_EXECUTOR_MAX_AGE_SECONDS,
    )


def _format_read_output(output: dict[str, Any], args: dict[str, Any], *, request_id: str) -> dict[str, Any] | None:
    content = output.get("content")
    if not isinstance(content, str):
        return None
    resolved_path = output.get("path", args.get("path"))
    if not isinstance(resolved_path, str):
        resolved_path = str(args.get("path", ""))
    size_bytes = output.get("size_bytes")
    if not isinstance(size_bytes, int):
        size_bytes = len(content.encode("utf-8"))
    line_count = output.get("line_count")
    if not isinstance(line_count, int):
        line_count = content.count("\n") + 1 if content else 1
    return {
        "path": resolved_path,
        "content": content,
        "size_bytes": size_bytes,
        "encoding": "utf-8",
        "line_count": line_count,
        "truncated": bool(output.get("truncated", False)),
        "mime_type": output.get("mime_type"),
        "capability_request_id": request_id,
    }


def _format_list_output(output: dict[str, Any], args: dict[str, Any], *, request_id: str) -> dict[str, Any]:
    path_value = output.get("path", args.get("path", "."))
    if not isinstance(path_value, str):
        path_value = str(args.get("path", "."))
    raw_entries = output.get("entries")
    entries: list[dict[str, Any]] = []
    if isinstance(raw_entries, list):
        for item in raw_entries:
            if isinstance(item, str):
                entries.append(
                    {
                        "name": item,
                        "path": item,
                        "type": "other",
                        "size_bytes": 0,
                        "modified_at": None,
                    }
                )
            elif isinstance(item, dict):
                entries.append(item)
    return {
        "path": path_value,
        "entries": entries,
        "total_files": int(output.get("total_files", 0)) if isinstance(output.get("total_files", 0), int) else 0,
        "total_dirs": int(output.get("total_dirs", 0)) if isinstance(output.get("total_dirs", 0), int) else 0,
        "truncated": bool(output.get("truncated", False)),
        "capability_request_id": request_id,
    }


def _format_search_output(output: dict[str, Any], args: dict[str, Any], *, request_id: str) -> dict[str, Any]:
    return {
        "query": output.get("query", args.get("query", "")),
        "matches": output.get("matches", []),
        "total_matches": output.get("total_matches", 0),
        "search_duration_seconds": output.get("search_duration_seconds", 0),
        "capability_request_id": request_id,
    }


def _dispatch_browser_capability_raw(
    capability: str,
    args: dict[str, Any],
    *,
    timeout_seconds: float = 15.0,
) -> dict[str, Any] | None:
    if not _has_recent_desktop_executor():
        return None

    result = dispatch_and_wait(
        CapabilityDispatchRequest(
            capability=capability,
            args=args,
            risk_level=RiskLevel.SAFE if capability in {"browser.snapshot", "browser.extract", "browser.close"} else RiskLevel.RESTRICTED,
            requires_approval=False,
        ),
        timeout_seconds=timeout_seconds,
        poll_interval_seconds=0.2,
    )
    if result is None:
        return None
    if not result.ok:
        if result.error_code == "not_supported":
            return None
        return {
            "error": result.error_message or result.error_code or "capability execution failed",
            "capability_request_id": result.request_id,
        }

    output = result.output if isinstance(result.output, dict) else {}
    return output


def try_dispatch_browser_capability(
    capability: str,
    args: dict[str, Any],
    *,
    timeout_seconds: float = 15.0,
) -> dict[str, Any] | None:
    if capability == "browser.open":
        return _try_dispatch_browser_open_with_snapshot(args, timeout_seconds=timeout_seconds)

    raw = _dispatch_browser_capability_raw(capability, args, timeout_seconds=timeout_seconds)
    if raw is None:
        return None

    formatted: dict[str, Any] | None = None
    if capability == "browser.snapshot":
        formatted = format_browser_snapshot_output(raw, request_id="")
    elif capability == "browser.extract":
        formatted = format_browser_extract_output(raw, request_id="")
    elif capability == "browser.close":
        formatted = format_browser_close_output(raw, request_id="")

    if formatted is not None:
        save_browser_experience(capability, formatted)
        return formatted

    return raw


def _try_dispatch_browser_open_with_snapshot(
    args: dict[str, Any],
    *,
    timeout_seconds: float = 15.0,
) -> dict[str, Any] | None:
    open_raw = _dispatch_browser_capability_raw("browser.open", args, timeout_seconds=timeout_seconds)
    if open_raw is None:
        return None

    if isinstance(open_raw, dict) and "error" in open_raw:
        return open_raw

    session_id = open_raw.get("session_id") if isinstance(open_raw, dict) else None
    if not session_id:
        formatted = format_browser_open_output(open_raw, request_id="")
        save_browser_experience("browser.open", formatted)
        return formatted

    snapshot_raw = _dispatch_browser_capability_raw(
        "browser.snapshot",
        {"session_id": session_id, "include_text": True},
        timeout_seconds=timeout_seconds,
    )

    merged = merge_browser_open_with_snapshot(open_raw, snapshot_raw if isinstance(snapshot_raw, dict) else None, request_id="")
    save_browser_experience("browser.open", merged)
    return merged


def set_memory_repository_getter(getter: Callable[[], MemoryRepository | None]) -> None:
    set_browser_memory_repository_getter(getter)


# ── Browser organ call helpers ────────────────────────────────────────────────


class BrowserOrganUnavailable(Exception):
    """Raised when the browser organ is not available."""

    pass


class BrowserCapabilityError(Exception):
    """Raised when a browser capability call fails."""

    def __init__(self, message: str, capability_request_id: str | None = None):
        super().__init__(message)
        self.capability_request_id = capability_request_id


def call_browser_capability(
    capability: str,
    args: dict[str, Any],
    *,
    timeout_seconds: float = 15.0,
) -> dict[str, Any]:
    """Call browser organ, raising if unavailable or failed."""
    raw = try_dispatch_browser_capability(capability, args, timeout_seconds=timeout_seconds)
    if raw is None:
        raise BrowserOrganUnavailable(f"browser organ unavailable for {capability}")
    if "error" in raw:
        raise BrowserCapabilityError(
            raw.get("error", "unknown"), raw.get("capability_request_id")
        )
    return raw
