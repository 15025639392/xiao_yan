from __future__ import annotations

import json
from pathlib import Path
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException, Request
import httpx
from uuid import uuid4

from app.api.deps import (
    get_chat_gateway,
    get_goal_repository,
    get_memory_repository,
    get_memory_service,
    get_persona_service,
    get_state_store,
)
from app.goals.repository import GoalRepository
from app.capabilities.models import CapabilityDispatchRequest, RiskLevel
from app.capabilities.runtime import dispatch_and_wait, has_recent_capability_executor
from app.llm.gateway import ChatGateway
from app.llm.schemas import (
    ChatMessage,
    ChatRequest,
    ChatResumeRequest,
    ChatSubmissionResult,
)
from app.memory.repository import MemoryRepository
from app.memory.service import MemoryService
from app.persona.expression_mapper import ExpressionStyleMapper
from app.persona.prompt_builder import build_chat_instructions
from app.persona.service import PersonaService
from app.runtime import StateStore
from app.runtime_ext.bootstrap import build_chat_messages, find_latest_today_plan_completion
from app.runtime_ext.runtime_config import FolderAccessLevel, get_runtime_config

CHAT_FILE_TOOL_DEFINITIONS = [
    {
        "type": "function",
        "name": "read_file",
        "description": "Read a file and return its content. Use absolute paths when possible.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "max_bytes": {"type": "integer", "minimum": 1, "maximum": 2 * 1024 * 1024},
            },
            "required": ["path"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "list_directory",
        "description": "List files and directories under a path.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "recursive": {"type": "boolean"},
                "pattern": {"type": "string"},
            },
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "search_files",
        "description": "Search text in files under a path.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "search_path": {"type": "string"},
                "file_pattern": {"type": "string"},
                "max_results": {"type": "integer", "minimum": 1, "maximum": 200},
            },
            "required": ["query"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "write_file",
        "description": "Write UTF-8 text to a file path. Requires full_access for granted folders.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"},
                "create_dirs": {"type": "boolean"},
            },
            "required": ["path", "content"],
            "additionalProperties": False,
        },
    },
]


class FolderPermissionEntry(BaseModel):
    path: str = Field(..., min_length=1)
    access_level: FolderAccessLevel


class FolderPermissionRequest(BaseModel):
    path: str = Field(..., min_length=1)
    access_level: FolderAccessLevel


class FolderPermissionListResponse(BaseModel):
    permissions: list[FolderPermissionEntry]


def build_chat_router() -> APIRouter:
    router = APIRouter()

    def _summarize_latest_self_programming(state) -> str | None:
        job = state.self_programming_job
        if job is None:
            return None
        if job.status.value == "applied":
            return f"我补强了 {job.target_area}，并通过了验证。"
        if job.status.value == "failed":
            return f"我尝试补强 {job.target_area}，但还没通过验证。"
        return None

    def _merge_chat_stream_content(current_content: str, delta: str) -> str:
        if not current_content:
            return delta
        if not delta:
            return current_content
        if delta.startswith(current_content):
            return delta
        if current_content.startswith(delta) or delta in current_content:
            return current_content
        max_overlap = min(len(current_content), len(delta))
        for overlap in range(max_overlap, 0, -1):
            if current_content[-overlap:] == delta[:overlap]:
                return f"{current_content}{delta[overlap:]}"
        return f"{current_content}{delta}"

    def _build_resume_instruction(partial_content: str) -> str:
        return (
            "这是一次失败后的继续生成。"
            "你必须紧接着下面这段 assistant 已输出内容继续生成，"
            "不要重复已经说过的文字，不要重开话题，不要改写前文。\n\n"
            f"已输出内容：\n{partial_content}"
        )

    def _should_fallback_to_stream_without_tools(exception: Exception) -> bool:
        if not isinstance(exception, httpx.HTTPStatusError):
            return False
        status_code = exception.response.status_code if exception.response is not None else None
        return status_code in {400, 404, 405, 415, 422, 501}

    def _normalize_folder_path(raw_path: str) -> Path:
        path = Path(raw_path).expanduser()
        if not path.is_absolute():
            raise HTTPException(status_code=400, detail="folder path must be absolute")
        return path.resolve()

    def _build_folder_permission_response() -> FolderPermissionListResponse:
        config = get_runtime_config()
        entries = [
            FolderPermissionEntry(path=path, access_level=access_level)
            for path, access_level in config.list_folder_permissions()
        ]
        return FolderPermissionListResponse(permissions=entries)

    def _file_policy_args() -> dict:
        config = get_runtime_config()
        return {"file_policy": config.get_capability_file_policy()}

    def _run_chat_submission(
        *,
        request: Request,
        gateway: ChatGateway,
        chat_messages: list[ChatMessage],
        instructions: str,
        assistant_message_id: str,
        initial_output_text: str = "",
    ) -> tuple[ChatSubmissionResult, str]:
        response_id: str | None = None
        output_text = initial_output_text
        started = False
        hub = getattr(request.app.state, "realtime_hub", None)

        try:
            for event in gateway.stream_response(chat_messages, instructions=instructions):
                event_type = event["type"]
                if event_type == "response_started":
                    response_id = event.get("response_id") or response_id
                    if hub is not None and not started:
                        hub.publish_chat_started(assistant_message_id, response_id=response_id)
                        started = True
                    continue

                if event_type == "text_delta":
                    if hub is not None and not started:
                        hub.publish_chat_started(assistant_message_id, response_id=response_id)
                        started = True

                    delta = event.get("delta") or ""
                    if not delta:
                        continue

                    output_text = _merge_chat_stream_content(output_text, delta)
                    if hub is not None:
                        hub.publish_chat_delta(assistant_message_id, delta)
                    continue

                if event_type == "response_completed":
                    response_id = event.get("response_id") or response_id
                    completed_output_text = event.get("output_text") or ""
                    if completed_output_text and completed_output_text not in output_text:
                        output_text = completed_output_text
                    continue

                if event_type == "response_failed":
                    error_message = event.get("error") or "streaming failed"
                    if hub is not None:
                        hub.publish_chat_failed(assistant_message_id, error_message)
                    raise HTTPException(status_code=502, detail=error_message)
        except httpx.HTTPStatusError as exception:
            detail = str(exception)
            try:
                if exception.response is not None:
                    detail = exception.response.text or detail
            except Exception:  # noqa: BLE001
                pass
            if hub is not None:
                hub.publish_chat_failed(assistant_message_id, detail)
            raise HTTPException(status_code=502, detail=detail) from exception
        except HTTPException:
            raise
        except Exception as exception:
            if hub is not None:
                hub.publish_chat_failed(assistant_message_id, str(exception))
            raise HTTPException(status_code=502, detail=str(exception)) from exception

        if hub is not None and not started:
            hub.publish_chat_started(assistant_message_id, response_id=response_id)
        if hub is not None:
            hub.publish_chat_completed(assistant_message_id, response_id, output_text)

        return (
            ChatSubmissionResult(
                response_id=response_id,
                assistant_message_id=assistant_message_id,
            ),
            output_text,
        )

    def _build_chat_file_tools():
        from app.tools.file_tools import FileTools

        workspace = Path(__file__).resolve().parents[4]
        config = get_runtime_config()
        granted_folders = {path: access_level for path, access_level in config.list_folder_permissions()}
        return FileTools(
            allowed_base_path=workspace,
            folder_permissions=granted_folders,
        )

    def _execute_file_tool_call(file_tools, tool_name: str, arguments: dict) -> str:
        def _try_dispatch(tool: str, args: dict) -> str | None:
            if not has_recent_capability_executor("desktop", max_age_seconds=10):
                return None

            capability_map = {
                "read_file": ("fs.read", RiskLevel.SAFE, False),
                "list_directory": ("fs.list", RiskLevel.SAFE, False),
                "search_files": ("fs.search", RiskLevel.RESTRICTED, False),
                "write_file": ("fs.write", RiskLevel.RESTRICTED, True),
            }
            mapping = capability_map.get(tool)
            if mapping is None:
                return None

            capability, risk_level, requires_approval = mapping
            result = dispatch_and_wait(
                CapabilityDispatchRequest(
                    capability=capability,
                    args={**args, **_file_policy_args()},
                    risk_level=risk_level,
                    requires_approval=requires_approval,
                ),
                timeout_seconds=0.8,
                poll_interval_seconds=0.05,
            )

            # timeout: fallback to existing core-local execution
            if result is None:
                return None

            if not result.ok:
                if result.error_code == "not_supported":
                    return None
                return json.dumps(
                    {
                        "error": result.error_message or result.error_code or "capability execution failed",
                        "capability_request_id": result.request_id,
                    },
                    ensure_ascii=False,
                )

            output = result.output if isinstance(result.output, dict) else {}
            if tool == "read_file":
                content = output.get("content")
                if not isinstance(content, str):
                    return json.dumps(
                        {"error": "invalid capability output for read_file", "capability_request_id": result.request_id},
                        ensure_ascii=False,
                    )
                path_value = output.get("path", str(args.get("path", "")))
                if not isinstance(path_value, str):
                    path_value = str(args.get("path", ""))
                size_bytes = output.get("size_bytes")
                if not isinstance(size_bytes, int):
                    size_bytes = len(content.encode("utf-8"))
                line_count = output.get("line_count")
                if not isinstance(line_count, int):
                    line_count = content.count("\n") + 1 if content else 1
                payload = {
                    "path": path_value,
                    "content": content,
                    "size_bytes": size_bytes,
                    "encoding": "utf-8",
                    "line_count": line_count,
                    "truncated": bool(output.get("truncated", False)),
                    "capability_request_id": result.request_id,
                }
                return json.dumps(payload, ensure_ascii=False)

            if tool == "list_directory":
                path_value = output.get("path", str(args.get("path", ".")))
                if not isinstance(path_value, str):
                    path_value = str(args.get("path", "."))
                raw_entries = output.get("entries")
                entries = []
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
                payload = {
                    "path": path_value,
                    "entries": entries,
                    "total_files": 0,
                    "total_dirs": 0,
                    "truncated": bool(output.get("truncated", False)),
                    "capability_request_id": result.request_id,
                }
                return json.dumps(payload, ensure_ascii=False)

            if tool == "write_file":
                path_value = output.get("path", str(args.get("path", "")))
                if not isinstance(path_value, str):
                    path_value = str(args.get("path", ""))
                payload = {
                    "path": path_value,
                    "success": True,
                    "bytes_written": output.get("bytes_written"),
                    "capability_request_id": result.request_id,
                }
                return json.dumps(payload, ensure_ascii=False)

            if tool == "search_files":
                payload = {
                    "query": output.get("query", str(args.get("query", ""))),
                    "matches": output.get("matches", []),
                    "total_matches": output.get("total_matches", 0),
                    "search_duration_seconds": output.get("search_duration_seconds", 0),
                    "capability_request_id": result.request_id,
                }
                return json.dumps(payload, ensure_ascii=False)

            return None

        try:
            if tool_name == "read_file":
                path = str(arguments.get("path", ""))
                max_bytes = int(arguments.get("max_bytes", 512 * 1024))
                dispatched = _try_dispatch("read_file", {"path": path, "max_bytes": max_bytes})
                if dispatched is not None:
                    return dispatched
                result = file_tools.read_file(path, max_bytes=max_bytes)
                payload = result.to_dict()
                payload["content"] = result.content
                return json.dumps(payload, ensure_ascii=False)

            if tool_name == "list_directory":
                path = str(arguments.get("path", "."))
                recursive = bool(arguments.get("recursive", False))
                pattern = arguments.get("pattern")
                pattern_value = None if pattern is None else str(pattern)
                dispatched = _try_dispatch(
                    "list_directory",
                    {"path": path, "recursive": recursive, "pattern": pattern_value},
                )
                if dispatched is not None:
                    return dispatched
                result = file_tools.list_directory(path, recursive=recursive, pattern=pattern_value)
                return json.dumps(result.to_dict(), ensure_ascii=False)

            if tool_name == "search_files":
                query = str(arguments.get("query", ""))
                if not query:
                    return json.dumps({"error": "query is required"}, ensure_ascii=False)
                search_path = str(arguments.get("search_path", "."))
                file_pattern = str(arguments.get("file_pattern", "*.py"))
                max_results = int(arguments.get("max_results", 20))
                dispatched = _try_dispatch(
                    "search_files",
                    {
                        "query": query,
                        "search_path": search_path,
                        "file_pattern": file_pattern,
                        "max_results": max_results,
                    },
                )
                if dispatched is not None:
                    return dispatched
                result = file_tools.search_content(
                    query,
                    search_path,
                    file_pattern=file_pattern,
                    max_results=max_results,
                )
                return json.dumps(result.to_dict(), ensure_ascii=False)

            if tool_name == "write_file":
                path = str(arguments.get("path", ""))
                content = str(arguments.get("content", ""))
                create_dirs = bool(arguments.get("create_dirs", True))
                dispatched = _try_dispatch(
                    "write_file",
                    {"path": path, "content": content, "create_dirs": create_dirs},
                )
                if dispatched is not None:
                    return dispatched
                result = file_tools.write_file(path, content, create_dirs=create_dirs)
                return json.dumps(result.to_dict(), ensure_ascii=False)

            return json.dumps({"error": f"unknown tool: {tool_name}"}, ensure_ascii=False)
        except Exception as exception:  # noqa: BLE001
            return json.dumps({"error": str(exception)}, ensure_ascii=False)

    def _extract_function_calls(response_payload: dict) -> list[tuple[str, str, dict]]:
        calls: list[tuple[str, str, dict]] = []
        output_items = response_payload.get("output", [])
        if not isinstance(output_items, list):
            return calls

        for item in output_items:
            if not isinstance(item, dict):
                continue
            if item.get("type") != "function_call":
                continue

            call_id = item.get("call_id")
            tool_name = item.get("name")
            raw_arguments = item.get("arguments", "{}")
            if not isinstance(call_id, str) or not isinstance(tool_name, str):
                continue

            arguments: dict = {}
            if isinstance(raw_arguments, str):
                try:
                    parsed = json.loads(raw_arguments)
                    if isinstance(parsed, dict):
                        arguments = parsed
                except json.JSONDecodeError:
                    arguments = {}
            elif isinstance(raw_arguments, dict):
                arguments = raw_arguments

            calls.append((call_id, tool_name, arguments))

        return calls

    def _extract_output_text(response_payload: dict) -> str:
        if isinstance(response_payload.get("output_text"), str):
            return response_payload["output_text"]

        output_items = response_payload.get("output", [])
        if not isinstance(output_items, list):
            return ""

        for item in output_items:
            if not isinstance(item, dict):
                continue
            if item.get("type") != "message":
                continue
            for content_item in item.get("content", []):
                if not isinstance(content_item, dict):
                    continue
                content_type = content_item.get("type")
                if content_type not in {"output_text", "text"}:
                    continue
                text = content_item.get("text")
                if isinstance(text, str) and text:
                    return text
        return ""

    def _run_chat_submission_with_tools(
        *,
        request: Request,
        gateway: ChatGateway,
        chat_messages: list[ChatMessage],
        instructions: str,
        assistant_message_id: str,
        initial_output_text: str = "",
    ) -> tuple[ChatSubmissionResult, str]:
        create_with_tools = getattr(gateway, "create_response_with_tools", None)
        if not callable(create_with_tools):
            return _run_chat_submission(
                request=request,
                gateway=gateway,
                chat_messages=chat_messages,
                instructions=instructions,
                assistant_message_id=assistant_message_id,
                initial_output_text=initial_output_text,
            )

        hub = getattr(request.app.state, "realtime_hub", None)
        started = False
        response_id: str | None = None

        file_tools = _build_chat_file_tools()
        accumulated_input: list[dict] = [message.model_dump() for message in chat_messages]
        # Lightweight diagnostics: helps identify "content too large" cases in provider errors.
        payload_hint = f"messages={len(chat_messages)}, instructions_chars={len(instructions or '')}"

        try:
            for _ in range(8):
                try:
                    response_payload = create_with_tools(
                        accumulated_input,
                        instructions=instructions,
                        tools=CHAT_FILE_TOOL_DEFINITIONS,
                    )
                except Exception as exception:  # noqa: BLE001
                    # Some providers reject tool payloads; degrade to plain streaming instead of hard failing.
                    if (
                        not started
                        and len(accumulated_input) == len(chat_messages)
                        and _should_fallback_to_stream_without_tools(exception)
                    ):
                        return _run_chat_submission(
                            request=request,
                            gateway=gateway,
                            chat_messages=chat_messages,
                            instructions=instructions,
                            assistant_message_id=assistant_message_id,
                            initial_output_text=initial_output_text,
                        )
                    raise
                if not isinstance(response_payload, dict):
                    raise HTTPException(status_code=502, detail="invalid gateway response payload")

                current_response_id = response_payload.get("id")
                if isinstance(current_response_id, str):
                    response_id = current_response_id

                function_calls = _extract_function_calls(response_payload)
                if not function_calls:
                    output_text = _extract_output_text(response_payload)
                    if initial_output_text:
                        output_text = _merge_chat_stream_content(initial_output_text, output_text)

                    # Some providers may return an empty non-stream tool response even when normal
                    # streaming works. On the first turn, degrade to plain streaming to avoid
                    # returning an empty assistant reply.
                    if (
                        not output_text
                        and not started
                        and len(accumulated_input) == len(chat_messages)
                    ):
                        return _run_chat_submission(
                            request=request,
                            gateway=gateway,
                            chat_messages=chat_messages,
                            instructions=instructions,
                            assistant_message_id=assistant_message_id,
                            initial_output_text=initial_output_text,
                        )

                    if not output_text:
                        raise HTTPException(status_code=502, detail="empty gateway response payload")

                    if hub is not None and not started:
                        hub.publish_chat_started(assistant_message_id, response_id=response_id)
                        started = True

                    if hub is not None and output_text:
                        hub.publish_chat_delta(assistant_message_id, output_text)
                    if hub is not None:
                        hub.publish_chat_completed(assistant_message_id, response_id, output_text)

                    return (
                        ChatSubmissionResult(
                            response_id=response_id,
                            assistant_message_id=assistant_message_id,
                        ),
                        output_text,
                    )

                if hub is not None and not started:
                    hub.publish_chat_started(assistant_message_id, response_id=response_id)
                    started = True

                tool_outputs: list[dict[str, str]] = []
                for call_id, tool_name, arguments in function_calls:
                    tool_output = _execute_file_tool_call(file_tools, tool_name, arguments)
                    tool_outputs.append(
                        {
                            "type": "function_call_output",
                            "call_id": call_id,
                            "output": tool_output,
                        }
                    )

                response_outputs = response_payload.get("output", [])
                if isinstance(response_outputs, list):
                    for output_item in response_outputs:
                        if isinstance(output_item, dict):
                            accumulated_input.append(output_item)

                accumulated_input.extend(tool_outputs)

            raise HTTPException(status_code=502, detail="tool call recursion limit exceeded")
        except HTTPException:
            if hub is not None and started:
                hub.publish_chat_failed(assistant_message_id, "tool execution failed")
            raise
        except httpx.HTTPStatusError as exception:
            detail = str(exception)
            try:
                if exception.response is not None:
                    detail = exception.response.text or detail
            except Exception:  # noqa: BLE001
                pass
            if hub is not None and started:
                hub.publish_chat_failed(assistant_message_id, f"{payload_hint}; {detail}")
            raise HTTPException(status_code=502, detail=f"{payload_hint}; {detail}") from exception
        except Exception as exception:  # noqa: BLE001
            if hub is not None and started:
                hub.publish_chat_failed(assistant_message_id, str(exception))
            raise HTTPException(status_code=502, detail=str(exception)) from exception

    @router.get("/chat/folder-permissions")
    def get_folder_permissions() -> FolderPermissionListResponse:
        return _build_folder_permission_response()

    @router.put("/chat/folder-permissions")
    def upsert_folder_permission(request_body: FolderPermissionRequest) -> FolderPermissionListResponse:
        folder_path = _normalize_folder_path(request_body.path)
        if not folder_path.exists():
            raise HTTPException(status_code=404, detail="folder not found")
        if not folder_path.is_dir():
            raise HTTPException(status_code=400, detail="path is not a directory")

        config = get_runtime_config()
        config.set_folder_permission(str(folder_path), request_body.access_level)
        return _build_folder_permission_response()

    @router.delete("/chat/folder-permissions")
    def remove_folder_permission(path: str) -> FolderPermissionListResponse:
        folder_path = _normalize_folder_path(path)
        config = get_runtime_config()
        removed = config.remove_folder_permission(str(folder_path))
        if not removed:
            raise HTTPException(status_code=404, detail="folder permission not found")
        return _build_folder_permission_response()

    @router.post("/chat")
    def chat(
        request_body: ChatRequest,
        request: Request,
        gateway: ChatGateway = Depends(get_chat_gateway),
        memory_repository: MemoryRepository = Depends(get_memory_repository),
        state_store: StateStore = Depends(get_state_store),
        goal_repository: GoalRepository = Depends(get_goal_repository),
        persona_service: PersonaService = Depends(get_persona_service),
        memory_service: MemoryService = Depends(get_memory_service),
    ) -> ChatSubmissionResult:
        state = state_store.get()
        focus_goal = None if not state.active_goal_ids else goal_repository.get_goal(state.active_goal_ids[0])
        latest_plan_completion = find_latest_today_plan_completion(memory_repository)
        latest_self_programming = _summarize_latest_self_programming(state)

        persona_system_prompt = persona_service.build_system_prompt()
        persona_service.infer_chat_emotion(request_body.message)

        memory_context = memory_service.build_memory_prompt_context(
            user_message=request_body.message,
            max_chars=600,
            persona_values=persona_service.profile.values,
        )
        relationship_summary = memory_service.get_relationship_summary()

        current_emotion = persona_service.profile.emotion
        style_mapper = ExpressionStyleMapper(personality=persona_service.profile.personality)
        style_override = style_mapper.map_from_state(current_emotion)
        expression_style_context = style_mapper.build_style_prompt(style_override)

        config = get_runtime_config()
        gateway.model = config.chat_model
        chat_messages = build_chat_messages(
            memory_repository,
            state_store,
            goal_repository,
            request_body.message,
            limit=config.chat_context_limit,
        )
        instructions = build_chat_instructions(
            focus_goal_title=None if focus_goal is None else focus_goal.title,
            latest_plan_completion=latest_plan_completion,
            latest_self_programming=latest_self_programming,
            user_message=request_body.message,
            persona_system_prompt=persona_system_prompt,
            relationship_summary=relationship_summary,
            memory_context=memory_context or None,
            expression_style_context=expression_style_context or None,
            folder_permissions=config.list_folder_permissions(),
        )

        assistant_message_id = f"assistant_{uuid4().hex}"
        submission, output_text = _run_chat_submission_with_tools(
            request=request,
            gateway=gateway,
            chat_messages=chat_messages,
            instructions=instructions,
            assistant_message_id=assistant_message_id,
        )

        extracted = memory_service.extract_from_conversation(
            user_message=request_body.message,
            assistant_response=output_text,
            assistant_session_id=assistant_message_id,
        )
        for entry in extracted:
            memory_service.save(entry)

        return submission

    @router.post("/chat/resume")
    def resume_chat(
        request_body: ChatResumeRequest,
        request: Request,
        gateway: ChatGateway = Depends(get_chat_gateway),
        memory_repository: MemoryRepository = Depends(get_memory_repository),
        state_store: StateStore = Depends(get_state_store),
        goal_repository: GoalRepository = Depends(get_goal_repository),
        persona_service: PersonaService = Depends(get_persona_service),
        memory_service: MemoryService = Depends(get_memory_service),
    ) -> ChatSubmissionResult:
        state = state_store.get()
        focus_goal = None if not state.active_goal_ids else goal_repository.get_goal(state.active_goal_ids[0])
        latest_plan_completion = find_latest_today_plan_completion(memory_repository)
        latest_self_programming = _summarize_latest_self_programming(state)

        persona_system_prompt = persona_service.build_system_prompt()
        persona_service.infer_chat_emotion(request_body.message)
        memory_context = memory_service.build_memory_prompt_context(
            user_message=request_body.message,
            max_chars=600,
            persona_values=persona_service.profile.values,
        )
        relationship_summary = memory_service.get_relationship_summary()
        current_emotion = persona_service.profile.emotion
        style_mapper = ExpressionStyleMapper(personality=persona_service.profile.personality)
        style_override = style_mapper.map_from_state(current_emotion)
        expression_style_context = style_mapper.build_style_prompt(style_override)

        config = get_runtime_config()
        gateway.model = config.chat_model
        chat_messages = build_chat_messages(
            memory_repository,
            state_store,
            goal_repository,
            request_body.message,
            limit=config.chat_context_limit,
        )
        instructions = build_chat_instructions(
            focus_goal_title=None if focus_goal is None else focus_goal.title,
            latest_plan_completion=latest_plan_completion,
            latest_self_programming=latest_self_programming,
            user_message=request_body.message,
            persona_system_prompt=persona_system_prompt,
            relationship_summary=relationship_summary,
            memory_context=memory_context or None,
            expression_style_context=expression_style_context or None,
            folder_permissions=config.list_folder_permissions(),
        )
        instructions = f"{instructions}\n\n{_build_resume_instruction(request_body.partial_content)}"

        submission, output_text = _run_chat_submission_with_tools(
            request=request,
            gateway=gateway,
            chat_messages=chat_messages,
            instructions=instructions,
            assistant_message_id=request_body.assistant_message_id,
            initial_output_text=request_body.partial_content,
        )

        extracted = memory_service.extract_from_conversation(
            user_message=request_body.message,
            assistant_response=output_text,
            assistant_session_id=request_body.assistant_message_id,
        )
        for entry in extracted:
            memory_service.save(entry)

        return submission

    return router
