from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel

from app.tools.runner import CommandRunner
from app.tools.sandbox import CommandSandbox, ToolSafetyLevel

_tool_runner_instance: CommandRunner | None = None
_file_tools_instance = None


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


def _get_file_tools():
    global _file_tools_instance
    if _file_tools_instance is None:
        from app.tools.file_tools import FileTools

        workspace = Path(__file__).resolve().parents[4]
        _file_tools_instance = FileTools(allowed_base_path=workspace)
    return _file_tools_instance


class ToolExecuteRequest(BaseModel):
    command: str
    timeout_override: float | None = None


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
        runner = _get_command_runner()

        original_timeout = runner.timeout_seconds
        if request.timeout_override and request.timeout_override > 0:
            runner.timeout_seconds = min(request.timeout_override, 120.0)

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
        ft = _get_file_tools()
        result = ft.read_file(path, max_bytes=max_bytes)
        return result.to_dict()

    @router.get("/tools/files/list")
    def api_list_directory(path: str = ".", recursive: bool = False, pattern: str | None = None) -> dict:
        ft = _get_file_tools()
        result = ft.list_directory(path, recursive=recursive, pattern=pattern)
        return result.to_dict()

    @router.get("/tools/files/search")
    def api_search_files(
        query: str, search_path: str = ".", file_pattern: str = "*.py", max_results: int = 20
    ) -> dict:
        ft = _get_file_tools()
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

