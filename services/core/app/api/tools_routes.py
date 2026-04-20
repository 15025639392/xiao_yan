from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel

from app.api.file_tool_helpers import build_file_tools
from app.api.tool_capability_bridge import try_dispatch_file_capability, try_dispatch_shell_capability, try_dispatch_browser_capability
from app.tools.runner import CommandRunner
from app.tools.sandbox import CommandSandbox, ToolSafetyLevel

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


def build_tools_router() -> APIRouter:
    router = APIRouter()

    @router.get("/tools")
    def list_tools() -> dict:
        runner = _get_command_runner()
        return list_tools_response(runner)

    @router.post("/tools/execute")
    def execute_tool(request: ToolExecuteRequest) -> dict:
        timeout_override = 60.0
        if request.timeout_override and request.timeout_override > 0:
            timeout_override = min(request.timeout_override, 120.0)

        runner = _get_command_runner()
        capability_dispatched = try_dispatch_shell_capability(
            request.command,
            runner=runner,
            wait_timeout_seconds=0.6,
            command_timeout_seconds=timeout_override,
        )
        if capability_dispatched is not None:
            return capability_dispatched.to_dict()

        original_timeout = runner.timeout_seconds
        runner.timeout_seconds = timeout_override

        result = runner.run(request.command)
        runner.timeout_seconds = original_timeout
        return {**result.to_dict()}

    @router.get("/tools/history")
    def get_tool_history(limit: int = 30) -> dict:
        runner = _get_command_runner()
        return tool_history_response(runner, limit=limit)

    @router.delete("/tools/history")
    def clear_tool_history() -> dict:
        runner = _get_command_runner()
        return clear_tool_history_response(runner)

    @router.get("/tools/files/read")
    def api_read_file(path: str, max_bytes: int = 512 * 1024) -> dict:
        capability_result = try_dispatch_file_capability(
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
        capability_result = try_dispatch_file_capability(
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
        capability_result = try_dispatch_file_capability(
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
        return tool_status_response(runner)

    # --- Browser capability routes ---

    @router.post("/tools/browser/open")
    def api_browser_open(url: str, session_id: str | None = None, headless: bool | None = None) -> dict:
        result = try_dispatch_browser_capability(
            "browser.open",
            {"url": url, "session_id": session_id, "headless": headless},
        )
        if result is not None:
            return result
        return {"error": "browser.open: no desktop executor available", "capability_request_id": None}

    @router.post("/tools/browser/snapshot")
    def api_browser_snapshot(
        session_id: str,
        include_text: bool = True,
        include_accessibility: bool = False,
        include_screenshot: bool = False,
        max_text_bytes: int | None = None,
    ) -> dict:
        result = try_dispatch_browser_capability(
            "browser.snapshot",
            {
                "session_id": session_id,
                "include_text": include_text,
                "include_accessibility": include_accessibility,
                "include_screenshot": include_screenshot,
                "max_text_bytes": max_text_bytes,
            },
        )
        if result is not None:
            return result
        return {"error": "browser.snapshot: no desktop executor available", "capability_request_id": None}

    @router.post("/tools/browser/extract")
    def api_browser_extract(
        session_id: str,
        target: str,
        schema: dict | None = None,
        max_items: int | None = None,
    ) -> dict:
        result = try_dispatch_browser_capability(
            "browser.extract",
            {"session_id": session_id, "target": target, "schema": schema, "max_items": max_items},
        )
        if result is not None:
            return result
        return {"error": "browser.extract: no desktop executor available", "capability_request_id": None}

    @router.post("/tools/browser/close")
    def api_browser_close(session_id: str) -> dict:
        result = try_dispatch_browser_capability(
            "browser.close",
            {"session_id": session_id},
        )
        if result is not None:
            return result
        return {"error": "browser.close: no desktop executor available", "capability_request_id": None}

    return router
