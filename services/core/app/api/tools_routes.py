from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel

from app.api.file_tool_helpers import build_file_tools, default_files_base_path, file_policy_args
from app.capabilities.models import CapabilityDispatchRequest, RiskLevel
from app.capabilities.runtime import dispatch_and_wait, has_recent_capability_executor
from app.runtime_ext.runtime_config import get_runtime_config
from app.tools.runner import CommandRunner
from app.tools.models import ToolExecutionResult
from app.tools.sandbox import CommandSandbox, SandboxViolation, ToolSafetyLevel

_tool_runner_instance: CommandRunner | None = None


def _get_command_runner() -> CommandRunner:
    global _tool_runner_instance
    if _tool_runner_instance is None:
        workspace = Path(__file__).resolve().parents[4]
        sandbox = CommandSandbox.with_defaults(
            max_level=ToolSafetyLevel.RESTRICTED,
            allowed_base_path=workspace,
        )
        _tool_runner_instance = CommandRunner(
            sandbox,
            working_directory=workspace,
            timeout_seconds=60.0,
        )
    return _tool_runner_instance


class ToolExecuteRequest(BaseModel):
    command: str
    timeout_override: float | None = None


def _try_dispatch_file_capability(
    capability: str,
    args: dict,
    *,
    timeout_seconds: float = 0.8,
) -> dict | None:
    if not has_recent_capability_executor("desktop", max_age_seconds=10):
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
        truncated = bool(output.get("truncated", False))
        return {
            "path": resolved_path,
            "content": content,
            "size_bytes": size_bytes,
            "encoding": "utf-8",
            "line_count": line_count,
            "truncated": truncated,
            "mime_type": output.get("mime_type"),
            "capability_request_id": result.request_id,
        }

    if capability == "fs.list":
        path_value = output.get("path", args.get("path", "."))
        if not isinstance(path_value, str):
            path_value = str(args.get("path", "."))
        raw_entries = output.get("entries")
        entries: list[dict] = []
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
            "capability_request_id": result.request_id,
        }

    if capability == "fs.search":
        if not isinstance(output, dict):
            return None
        payload = {
            "query": output.get("query", args.get("query", "")),
            "matches": output.get("matches", []),
            "total_matches": output.get("total_matches", 0),
            "search_duration_seconds": output.get("search_duration_seconds", 0),
            "capability_request_id": result.request_id,
        }
        return payload

    return None


def _try_dispatch_shell_capability(
    command: str,
    *,
    wait_timeout_seconds: float = 0.6,
    command_timeout_seconds: float = 60.0,
) -> ToolExecutionResult | None:
    runner = _get_command_runner()
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

    if not has_recent_capability_executor("desktop", max_age_seconds=10):
        return None

    config = get_runtime_config()
    shell_policy = config.get_capability_shell_policy()
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


def build_tools_router() -> APIRouter:
    router = APIRouter()

    @router.get("/tools")
    def list_tools() -> dict:
        runner = _get_command_runner()
        tools = runner.sandbox.list_available_tools()

        by_category: dict[str, list] = {}
        for t in tools:
            cat = t.category
            by_category.setdefault(cat, []).append(
                {
                    "name": t.name,
                    "description": t.description,
                    "safety_level": t.safety_level.value,
                    "examples": t.examples[:3],
                }
            )

        return {
            "total_count": len(tools),
            "by_category": by_category,
            "safety_levels": [sl.value for sl in ToolSafetyLevel],
        }

    @router.post("/tools/execute")
    def execute_tool(request: ToolExecuteRequest) -> dict:
        timeout_override = 60.0
        if request.timeout_override and request.timeout_override > 0:
            timeout_override = min(request.timeout_override, 120.0)

        capability_dispatched = _try_dispatch_shell_capability(
            request.command,
            wait_timeout_seconds=0.6,
            command_timeout_seconds=timeout_override,
        )
        if capability_dispatched is not None:
            return capability_dispatched.to_dict()

        runner = _get_command_runner()

        original_timeout = runner.timeout_seconds
        runner.timeout_seconds = timeout_override

        result = runner.run(request.command)
        runner.timeout_seconds = original_timeout
        return {**result.to_dict()}

    @router.get("/tools/history")
    def get_tool_history(limit: int = 30) -> dict:
        runner = _get_command_runner()
        return {
            "entries": runner.get_history(limit),
            "total": len(runner._history),
        }

    @router.delete("/tools/history")
    def clear_tool_history() -> dict:
        runner = _get_command_runner()
        count = runner.clear_history()
        return {"cleared": count, "message": f"已清除 {count} 条历史记录"}

    @router.get("/tools/files/read")
    def api_read_file(path: str, max_bytes: int = 512 * 1024) -> dict:
        capability_result = _try_dispatch_file_capability(
            "fs.read",
            {"path": path, "max_bytes": max_bytes},
        )
        if capability_result is not None:
            return capability_result

        ft = build_file_tools()
        result = ft.read_file(path, max_bytes=max_bytes)
        return result.to_dict()

    @router.get("/tools/files/list")
    def api_list_directory(path: str = ".", recursive: bool = False, pattern: str | None = None) -> dict:
        capability_result = _try_dispatch_file_capability(
            "fs.list",
            {"path": path, "recursive": recursive, "pattern": pattern},
        )
        if capability_result is not None:
            return capability_result

        ft = build_file_tools()
        result = ft.list_directory(path, recursive=recursive, pattern=pattern)
        return result.to_dict()

    @router.get("/tools/files/search")
    def api_search_files(
        query: str, search_path: str = ".", file_pattern: str = "*.py", max_results: int = 20
    ) -> dict:
        capability_result = _try_dispatch_file_capability(
            "fs.search",
            {
                "query": query,
                "search_path": search_path,
                "file_pattern": file_pattern,
                "max_results": max_results,
            },
        )
        if capability_result is not None:
            return capability_result

        ft = build_file_tools()
        result = ft.search_content(query, search_path, file_pattern=file_pattern, max_results=max_results)
        return result.to_dict()

    @router.get("/tools/status")
    def get_tools_status() -> dict:
        runner = _get_command_runner()
        history = runner.get_history(limit=1000)

        total_executions = len(runner._history)
        success_count = sum(1 for e in history if e["success"])
        failed_count = sum(1 for e in history if not e["success"])
        timeout_count = sum(1 for e in history if e.get("timed_out"))

        tool_usage: dict[str, int] = {}
        for entry in history:
            name = entry.get("tool_name", "unknown") or "unknown"
            tool_usage[name] = tool_usage.get(name, 0) + 1

        return {
            "sandbox_enabled": True,
            "allowed_command_count": len(runner.sandbox.allowed_commands),
            "safety_filter": "restricted",
            "working_directory": str(runner.working_directory or ""),
            "timeout_seconds": runner.timeout_seconds,
            "statistics": {
                "total_executions": total_executions,
                "success_count": success_count,
                "failed_count": failed_count,
                "timeout_count": timeout_count,
                "success_rate": round(success_count / max(total_executions, 1), 3),
            },
            "recently_used_tools": sorted(tool_usage.items(), key=lambda x: -x[1])[:10],
            "history_size": len(runner._history),
        }

    return router
