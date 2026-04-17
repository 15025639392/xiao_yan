from __future__ import annotations

from logging import getLogger
from time import perf_counter
from fastapi import APIRouter, Depends, HTTPException, Request
import httpx

from app.api.chat_attachments import (
    apply_user_content_to_messages,
    append_attachment_context,
    build_attachment_permission_paths,
    build_effective_user_message,
    build_user_content,
    resolve_attachment_paths,
)
from app.api.chat_context import (
    build_base_chat_instructions,
    extract_knowledge_references,
    prepare_chat_context,
    record_retrieval_observability,
)
from app.api.chat_config_helpers import (
    ChatMcpServerListResponse,
    FolderPermissionListResponse,
    FolderPermissionRequest,
    build_chat_mcp_registry,
    build_chat_mcp_server_response,
    build_folder_permission_response,
    normalize_folder_path,
)
from app.api.chat_postprocess import finalize_chat_submission
from app.api.chat_reasoning import ChatReasoningController
from app.api.chat_runtime_helpers import (
    get_observability_tracker,
    merge_chat_stream_content,
    should_fallback_to_stream_without_tools,
)
from app.api.file_tool_helpers import build_file_tools, file_policy_args
from app.api.chat_tool_calls import (
    build_function_call_signature,
    execute_tool_call,
    extract_function_calls,
    extract_output_text,
)
from app.api.deps import (
    get_chat_gateway,
    get_chat_memory_runtime,
    get_goal_repository,
    get_memory_repository,
    get_persona_service,
    get_state_store,
)
from app.api.chat_skills import ChatSkillEntry, ChatSkillListResponse, append_skill_context, discover_chat_skills
from app.config import get_chat_knowledge_extraction_enabled
from app.goals.repository import GoalRepository
from app.llm.gateway import ChatGateway
from app.llm.schemas import (
    ChatMessage,
    ChatReasoningState,
    ChatRequest,
    ChatResumeRequest,
    ChatSubmissionResult,
)
from app.memory.chat_memory_runtime import ChatMemoryRuntime
from app.memory.repository import MemoryRepository
from app.persona.service import PersonaService
from app.runtime import StateStore
from app.runtime_ext.runtime_config import get_runtime_config

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

logger = getLogger(__name__)

def build_chat_router() -> APIRouter:
    router = APIRouter()
    reasoning = ChatReasoningController(logger=logger, recovery_scan_limit=800)

    def _build_resume_instruction(partial_content: str) -> str:
        return (
            "这是一次失败后的继续生成。"
            "你必须紧接着下面这段 assistant 已输出内容继续生成，"
            "不要重复已经说过的文字，不要重开话题，不要改写前文。\n\n"
            f"已输出内容：\n{partial_content}"
        )

    def _run_chat_submission(
        *,
        request: Request,
        gateway: ChatGateway,
        chat_messages: list[ChatMessage],
        instructions: str,
        assistant_message_id: str,
        initial_output_text: str = "",
        suppress_started_event: bool = False,
        knowledge_references: list[dict[str, str | float | None]] | None = None,
        reasoning_session_id: str | None = None,
        reasoning_state: ChatReasoningState | None = None,
    ) -> tuple[ChatSubmissionResult, str]:
        response_id: str | None = None
        output_text = initial_output_text
        started = False
        hub = getattr(request.app.state, "realtime_hub", None)
        reasoning_payload = reasoning_state.model_dump(mode="json") if reasoning_state is not None else None

        try:
            for event in gateway.stream_response(chat_messages, instructions=instructions):
                event_type = event["type"]
                if event_type == "response_started":
                    response_id = event.get("response_id") or response_id
                    if hub is not None and not started and not suppress_started_event:
                        hub.publish_chat_started(
                            assistant_message_id,
                            response_id=response_id,
                            reasoning_session_id=reasoning_session_id,
                            reasoning_state=reasoning_payload,
                        )
                        started = True
                    continue

                if event_type == "text_delta":
                    if hub is not None and not started and not suppress_started_event:
                        hub.publish_chat_started(
                            assistant_message_id,
                            response_id=response_id,
                            reasoning_session_id=reasoning_session_id,
                            reasoning_state=reasoning_payload,
                        )
                        started = True

                    delta = event.get("delta") or ""
                    if not delta:
                        continue

                    output_text = merge_chat_stream_content(output_text, delta)
                    if hub is not None:
                        hub.publish_chat_delta(
                            assistant_message_id,
                            delta,
                            reasoning_session_id=reasoning_session_id,
                            reasoning_state=reasoning_payload,
                        )
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
                        hub.publish_chat_failed(
                            assistant_message_id,
                            error_message,
                            reasoning_session_id=reasoning_session_id,
                            reasoning_state=reasoning_payload,
                        )
                    raise HTTPException(status_code=502, detail=error_message)
        except httpx.HTTPStatusError as exception:
            detail = str(exception)
            try:
                if exception.response is not None:
                    detail = exception.response.text or detail
            except Exception:  # noqa: BLE001
                pass
            if hub is not None:
                hub.publish_chat_failed(
                    assistant_message_id,
                    detail,
                    reasoning_session_id=reasoning_session_id,
                    reasoning_state=reasoning_payload,
                )
            raise HTTPException(status_code=502, detail=detail) from exception
        except HTTPException:
            raise
        except Exception as exception:
            if hub is not None:
                hub.publish_chat_failed(
                    assistant_message_id,
                    str(exception),
                    reasoning_session_id=reasoning_session_id,
                    reasoning_state=reasoning_payload,
                )
            raise HTTPException(status_code=502, detail=str(exception)) from exception

        if hub is not None and not started and not suppress_started_event:
            hub.publish_chat_started(
                assistant_message_id,
                response_id=response_id,
                reasoning_session_id=reasoning_session_id,
                reasoning_state=reasoning_payload,
            )
        if hub is not None:
            hub.publish_chat_completed(
                assistant_message_id,
                response_id,
                output_text,
                knowledge_references=knowledge_references,
                reasoning_session_id=reasoning_session_id,
                reasoning_state=reasoning_payload,
            )

        return (
            ChatSubmissionResult(
                response_id=response_id,
                assistant_message_id=assistant_message_id,
            ),
            output_text,
        )

    def _run_chat_submission_with_tools(
        *,
        request: Request,
        gateway: ChatGateway,
        chat_messages: list[ChatMessage],
        instructions: str,
        assistant_message_id: str,
        initial_output_text: str = "",
        knowledge_references: list[dict[str, str | float | None]] | None = None,
        extra_tools: list[dict[str, object]] | None = None,
        mcp_registry: ChatMcpCallRegistry | None = None,
        reasoning_session_id: str | None = None,
        reasoning_state: ChatReasoningState | None = None,
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
                knowledge_references=knowledge_references,
                reasoning_session_id=reasoning_session_id,
                reasoning_state=reasoning_state,
            )

        hub = getattr(request.app.state, "realtime_hub", None)
        started = False
        response_id: str | None = None
        reasoning_payload = reasoning_state.model_dump(mode="json") if reasoning_state is not None else None

        file_tools = build_file_tools()
        tool_definitions = [*CHAT_FILE_TOOL_DEFINITIONS, *(extra_tools or [])]
        accumulated_input: list[dict] = [message.model_dump() for message in chat_messages]
        max_tool_rounds = 8
        tool_repeat_streak_limit = 3
        last_call_signature: str | None = None
        same_call_signature_streak = 0
        # Lightweight diagnostics: helps identify "content too large" cases in provider errors.
        payload_hint = f"messages={len(chat_messages)}, instructions_chars={len(instructions or '')}"

        def _fallback_without_tools(reason: str) -> tuple[ChatSubmissionResult, str]:
            fallback_instructions = (
                f"{instructions}\n\n"
                "[Tool fallback]\n"
                f"工具调用出现循环/超限（{reason}）。"
                "请不要再调用任何工具，直接基于已有上下文回答；"
                "如信息不足请明确说明不足点。"
            )
            return _run_chat_submission(
                request=request,
                gateway=gateway,
                chat_messages=chat_messages,
                instructions=fallback_instructions,
                assistant_message_id=assistant_message_id,
                initial_output_text=initial_output_text,
                suppress_started_event=started,
                knowledge_references=knowledge_references,
                reasoning_session_id=reasoning_session_id,
                reasoning_state=reasoning_state,
            )

        try:
            for _ in range(max_tool_rounds):
                try:
                    response_payload = create_with_tools(
                        accumulated_input,
                        instructions=instructions,
                        tools=tool_definitions,
                    )
                except Exception as exception:  # noqa: BLE001
                    # Some providers reject tool payloads; degrade to plain streaming instead of hard failing.
                    if (
                        not started
                        and len(accumulated_input) == len(chat_messages)
                        and should_fallback_to_stream_without_tools(exception)
                    ):
                        return _run_chat_submission(
                            request=request,
                            gateway=gateway,
                            chat_messages=chat_messages,
                            instructions=instructions,
                            assistant_message_id=assistant_message_id,
                            initial_output_text=initial_output_text,
                            knowledge_references=knowledge_references,
                            reasoning_session_id=reasoning_session_id,
                            reasoning_state=reasoning_state,
                        )
                    raise
                if not isinstance(response_payload, dict):
                    raise HTTPException(status_code=502, detail="invalid gateway response payload")

                current_response_id = response_payload.get("id")
                if isinstance(current_response_id, str):
                    response_id = current_response_id

                function_calls = extract_function_calls(response_payload)
                if not function_calls:
                    output_text = extract_output_text(response_payload)
                    if initial_output_text:
                        output_text = merge_chat_stream_content(initial_output_text, output_text)

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
                            knowledge_references=knowledge_references,
                            reasoning_session_id=reasoning_session_id,
                            reasoning_state=reasoning_state,
                        )

                    if not output_text:
                        raise HTTPException(status_code=502, detail="empty gateway response payload")

                    if hub is not None and not started:
                        hub.publish_chat_started(
                            assistant_message_id,
                            response_id=response_id,
                            reasoning_session_id=reasoning_session_id,
                            reasoning_state=reasoning_payload,
                        )
                        started = True

                    if hub is not None and output_text:
                        hub.publish_chat_delta(
                            assistant_message_id,
                            output_text,
                            reasoning_session_id=reasoning_session_id,
                            reasoning_state=reasoning_payload,
                        )
                    if hub is not None:
                        hub.publish_chat_completed(
                            assistant_message_id,
                            response_id,
                            output_text,
                            knowledge_references=knowledge_references,
                            reasoning_session_id=reasoning_session_id,
                            reasoning_state=reasoning_payload,
                        )

                    return (
                        ChatSubmissionResult(
                            response_id=response_id,
                            assistant_message_id=assistant_message_id,
                        ),
                        output_text,
                    )

                if hub is not None and not started:
                    hub.publish_chat_started(
                        assistant_message_id,
                        response_id=response_id,
                        reasoning_session_id=reasoning_session_id,
                        reasoning_state=reasoning_payload,
                    )
                    started = True

                call_signature = build_function_call_signature(function_calls)
                if call_signature == last_call_signature:
                    same_call_signature_streak += 1
                else:
                    same_call_signature_streak = 1
                    last_call_signature = call_signature
                if same_call_signature_streak >= tool_repeat_streak_limit:
                    return _fallback_without_tools("repeated_tool_calls")

                tool_outputs: list[dict[str, str]] = []
                for call_id, tool_name, arguments in function_calls:
                    tool_output = execute_tool_call(
                        file_tools,
                        tool_name,
                        arguments,
                        file_policy_args=file_policy_args(),
                        mcp_registry=mcp_registry,
                    )
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

            return _fallback_without_tools("tool_call_recursion_limit_exceeded")
        except HTTPException:
            if hub is not None and started:
                hub.publish_chat_failed(
                    assistant_message_id,
                    "tool execution failed",
                    reasoning_session_id=reasoning_session_id,
                    reasoning_state=reasoning_payload,
                )
            raise
        except httpx.HTTPStatusError as exception:
            detail = str(exception)
            try:
                if exception.response is not None:
                    detail = exception.response.text or detail
            except Exception:  # noqa: BLE001
                pass
            if hub is not None and started:
                hub.publish_chat_failed(
                    assistant_message_id,
                    f"{payload_hint}; {detail}",
                    reasoning_session_id=reasoning_session_id,
                    reasoning_state=reasoning_payload,
                )
            raise HTTPException(status_code=502, detail=f"{payload_hint}; {detail}") from exception
        except Exception as exception:  # noqa: BLE001
            if hub is not None and started:
                hub.publish_chat_failed(
                    assistant_message_id,
                    str(exception),
                    reasoning_session_id=reasoning_session_id,
                    reasoning_state=reasoning_payload,
                )
            raise HTTPException(status_code=502, detail=str(exception)) from exception

    @router.get("/chat/folder-permissions")
    def get_folder_permissions() -> FolderPermissionListResponse:
        return build_folder_permission_response()

    @router.get("/chat/skills")
    def get_chat_skills() -> ChatSkillListResponse:
        return ChatSkillListResponse(
            skills=[
                ChatSkillEntry(
                    name=str(skill.get("name", "")),
                    description=(
                        str(skill.get("description"))
                        if skill.get("description") is not None
                        else None
                    ),
                    path=str(skill.get("path", "")),
                    trigger_prefixes=[
                        str(prefix)
                        for prefix in (skill.get("trigger_prefixes") or [])
                        if isinstance(prefix, str)
                    ],
                )
                for skill in discover_chat_skills()
                if str(skill.get("name", "")).strip() and str(skill.get("path", "")).strip()
            ]
        )

    @router.get("/chat/mcp/servers")
    def get_chat_mcp_servers() -> ChatMcpServerListResponse:
        return build_chat_mcp_server_response()

    @router.put("/chat/folder-permissions")
    def upsert_folder_permission(request_body: FolderPermissionRequest) -> FolderPermissionListResponse:
        folder_path = normalize_folder_path(request_body.path)
        if not folder_path.exists():
            raise HTTPException(status_code=404, detail="folder not found")
        if not folder_path.is_dir():
            raise HTTPException(status_code=400, detail="path is not a directory")

        config = get_runtime_config()
        config.set_folder_permission(str(folder_path), request_body.access_level)
        return build_folder_permission_response()

    @router.delete("/chat/folder-permissions")
    def remove_folder_permission(path: str) -> FolderPermissionListResponse:
        folder_path = normalize_folder_path(path)
        config = get_runtime_config()
        removed = config.remove_folder_permission(str(folder_path))
        if not removed:
            raise HTTPException(status_code=404, detail="folder permission not found")
        return build_folder_permission_response()

    @router.post("/chat", response_model_exclude_none=True)
    def chat(
        request_body: ChatRequest,
        request: Request,
        gateway: ChatGateway = Depends(get_chat_gateway),
        state_store: StateStore = Depends(get_state_store),
        goal_repository: GoalRepository = Depends(get_goal_repository),
        memory_repository: MemoryRepository = Depends(get_memory_repository),
        persona_service: PersonaService = Depends(get_persona_service),
        chat_memory_runtime: ChatMemoryRuntime = Depends(get_chat_memory_runtime),
    ) -> ChatSubmissionResult:
        state = state_store.get()
        config = get_runtime_config()
        gateway.model = config.chat_model
        prepared_context = prepare_chat_context(
            chat_memory_runtime=chat_memory_runtime,
            context_limit=config.chat_context_limit,
            goal_repository=goal_repository,
            persona_service=persona_service,
            state=state,
            user_message=request_body.message,
        )
        attached_folder_paths = resolve_attachment_paths(request_body.attachments, "folder")
        attached_file_paths = resolve_attachment_paths(request_body.attachments, "file")
        attached_image_paths = resolve_attachment_paths(request_body.attachments, "image")

        for folder_path in build_attachment_permission_paths(
            folder_paths=attached_folder_paths,
            file_paths=attached_file_paths,
            image_paths=attached_image_paths,
        ):
            config.set_folder_permission(folder_path, "read_only")

        effective_user_message = build_effective_user_message(
            user_message=request_body.message,
            file_paths=attached_file_paths,
        )

        tracker = get_observability_tracker(request)
        retrieval_started_at = perf_counter()
        knowledge_references = extract_knowledge_references(prepared_context.memory_context)
        if prepared_context.retrieval_attempted:
            record_retrieval_observability(
                tracker=tracker,
                latency_ms=(perf_counter() - retrieval_started_at) * 1000.0,
                references=knowledge_references,
                failed=prepared_context.retrieval_failed,
            )
        user_content, image_parts = build_user_content(
            attachments=request_body.attachments,
            image_paths=attached_image_paths,
            provider_id=config.chat_provider,
            model=config.chat_model,
            user_message=effective_user_message,
            wire_api=getattr(gateway, "wire_api", "responses"),
        )
        chat_messages = apply_user_content_to_messages(
            prepared_context.chat_messages,
            user_content=user_content,
        )
        instructions = build_base_chat_instructions(
            folder_permissions=config.list_folder_permissions(),
            prepared=prepared_context,
            state=state,
            user_message=request_body.message,
        )
        instructions = append_attachment_context(
            instructions,
            folder_paths=attached_folder_paths,
            file_paths=attached_file_paths,
            image_paths=attached_image_paths,
        )
        instructions = append_skill_context(
            instructions,
            user_message=request_body.message,
            requested_skills=request_body.skills,
        )
        reasoning_state: ChatReasoningState | None = None
        reasoning_session_id: str | None = None
        if config.chat_continuous_reasoning_enabled and request_body.reasoning is not None and request_body.reasoning.enabled:
            reasoning_state = reasoning.start_reasoning_session(
                user_message=request_body.message,
                session_id=request_body.reasoning.session_id,
            )
            reasoning_session_id = reasoning_state.session_id
            instructions = reasoning.append_reasoning_instruction(
                instructions,
                reasoning_state=reasoning_state,
            )
        mcp_registry = build_chat_mcp_registry(request_body.mcp_servers)

        assistant_message_id = f"assistant_{uuid4().hex}"
        chat_started_at = perf_counter()
        if image_parts:
            submission, output_text = _run_chat_submission(
                request=request,
                gateway=gateway,
                chat_messages=chat_messages,
                instructions=instructions,
                assistant_message_id=assistant_message_id,
                knowledge_references=knowledge_references,
                reasoning_session_id=reasoning_session_id,
                reasoning_state=reasoning_state,
            )
        else:
            submission, output_text = _run_chat_submission_with_tools(
                request=request,
                gateway=gateway,
                chat_messages=chat_messages,
                instructions=instructions,
                assistant_message_id=assistant_message_id,
                knowledge_references=knowledge_references,
                extra_tools=mcp_registry.tools,
                mcp_registry=mcp_registry,
                reasoning_session_id=reasoning_session_id,
                reasoning_state=reasoning_state,
            )
        if tracker is not None:
            tracker.record_chat_latency((perf_counter() - chat_started_at) * 1000.0)

        return finalize_chat_submission(
            assistant_message_id=assistant_message_id,
            chat_memory_runtime=chat_memory_runtime,
            knowledge_extraction_enabled=get_chat_knowledge_extraction_enabled(),
            logger=logger,
            memory_repository=memory_repository,
            personality=persona_service.profile.personality,
            reasoning=reasoning,
            reasoning_state=reasoning_state,
            state_store=state_store,
            submission=submission,
            tracker=tracker,
            user_message=request_body.message,
            output_text=output_text,
        )

    @router.post("/chat/resume", response_model_exclude_none=True)
    def resume_chat(
        request_body: ChatResumeRequest,
        request: Request,
        gateway: ChatGateway = Depends(get_chat_gateway),
        state_store: StateStore = Depends(get_state_store),
        goal_repository: GoalRepository = Depends(get_goal_repository),
        memory_repository: MemoryRepository = Depends(get_memory_repository),
        persona_service: PersonaService = Depends(get_persona_service),
        chat_memory_runtime: ChatMemoryRuntime = Depends(get_chat_memory_runtime),
    ) -> ChatSubmissionResult:
        state = state_store.get()
        config = get_runtime_config()
        gateway.model = config.chat_model
        prepared_context = prepare_chat_context(
            chat_memory_runtime=chat_memory_runtime,
            context_limit=config.chat_context_limit,
            goal_repository=goal_repository,
            persona_service=persona_service,
            state=state,
            user_message=request_body.message,
        )
        tracker = get_observability_tracker(request)
        retrieval_started_at = perf_counter()
        knowledge_references = extract_knowledge_references(prepared_context.memory_context)
        if prepared_context.retrieval_attempted:
            record_retrieval_observability(
                tracker=tracker,
                latency_ms=(perf_counter() - retrieval_started_at) * 1000.0,
                references=knowledge_references,
                failed=prepared_context.retrieval_failed,
            )
        instructions = build_base_chat_instructions(
            folder_permissions=config.list_folder_permissions(),
            prepared=prepared_context,
            state=state,
            user_message=request_body.message,
        )
        resume_reasoning_session_id = (
            reasoning.resolve_resume_reasoning_session_id(request_body, memory_repository=memory_repository)
            if config.chat_continuous_reasoning_enabled
            else None
        )
        resume_reasoning_state: ChatReasoningState | None = None
        if resume_reasoning_session_id is not None:
            resume_reasoning_state = reasoning.start_reasoning_session(
                user_message=request_body.message,
                session_id=resume_reasoning_session_id,
            )
            instructions = reasoning.append_reasoning_instruction(
                instructions,
                reasoning_state=resume_reasoning_state,
            )

        instructions = f"{instructions}\n\n{_build_resume_instruction(request_body.partial_content)}"
        instructions = append_skill_context(
            instructions,
            user_message=request_body.message,
        )
        mcp_registry = build_chat_mcp_registry([])

        chat_started_at = perf_counter()
        submission, output_text = _run_chat_submission_with_tools(
            request=request,
            gateway=gateway,
            chat_messages=prepared_context.chat_messages,
            instructions=instructions,
            assistant_message_id=request_body.assistant_message_id,
            initial_output_text=request_body.partial_content,
            knowledge_references=knowledge_references,
            extra_tools=mcp_registry.tools,
            mcp_registry=mcp_registry,
            reasoning_session_id=resume_reasoning_state.session_id if resume_reasoning_state is not None else None,
            reasoning_state=resume_reasoning_state,
        )
        if tracker is not None:
            tracker.record_chat_latency((perf_counter() - chat_started_at) * 1000.0)

        return finalize_chat_submission(
            assistant_message_id=request_body.assistant_message_id,
            chat_memory_runtime=chat_memory_runtime,
            knowledge_extraction_enabled=get_chat_knowledge_extraction_enabled(),
            logger=logger,
            memory_repository=memory_repository,
            personality=persona_service.profile.personality,
            reasoning=reasoning,
            reasoning_state=resume_reasoning_state,
            state_store=state_store,
            submission=submission,
            tracker=tracker,
            user_message=request_body.message,
            output_text=output_text,
        )

    return router
