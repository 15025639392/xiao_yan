from __future__ import annotations

from app.tools.runner import CommandRunner
from app.tools.sandbox import ToolSafetyLevel


def list_tools_response(runner: CommandRunner) -> dict:
    tools = runner.sandbox.list_available_tools()
    by_category: dict[str, list] = {}
    for tool in tools:
        by_category.setdefault(tool.category, []).append(
            {
                "name": tool.name,
                "description": tool.description,
                "safety_level": tool.safety_level.value,
                "examples": tool.examples[:3],
            }
        )

    return {
        "total_count": len(tools),
        "by_category": by_category,
        "safety_levels": [level.value for level in ToolSafetyLevel],
    }


def tool_history_response(runner: CommandRunner, *, limit: int) -> dict:
    return {
        "entries": runner.get_history(limit),
        "total": len(runner._history),
    }


def clear_tool_history_response(runner: CommandRunner) -> dict:
    count = runner.clear_history()
    return {"cleared": count, "message": f"已清除 {count} 条历史记录"}


def tool_status_response(runner: CommandRunner) -> dict:
    history = runner.get_history(limit=1000)
    total_executions = len(runner._history)
    success_count = sum(1 for entry in history if entry["success"])
    failed_count = sum(1 for entry in history if not entry["success"])
    timeout_count = sum(1 for entry in history if entry.get("timed_out"))

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
        "recently_used_tools": sorted(tool_usage.items(), key=lambda item: -item[1])[:10],
        "history_size": len(runner._history),
    }
