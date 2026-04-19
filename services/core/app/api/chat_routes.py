from __future__ import annotations

from logging import getLogger
from time import perf_counter
from uuid import uuid4
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
from app.api.chat_runtime_helpers import get_observability_tracker, merge_chat_stream_content
from app.api.chat_submission_runner import (
    build_resume_instruction,
    run_chat_submission,
    run_chat_submission_with_tools,
)
from app.api.deps import (
    get_chat_gateway,
    get_chat_memory_runtime,
    get_memory_repository,
    get_persona_service,
    get_state_store,
)
from app.api.chat_skills import ChatSkillEntry, ChatSkillListResponse, append_skill_context, discover_chat_skills
from app.config import get_chat_knowledge_extraction_enabled
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

logger = getLogger(__name__)

def build_chat_router() -> APIRouter:
    router = APIRouter()
    reasoning = ChatReasoningController(logger=logger, recovery_scan_limit=800)

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
            user_timezone=request_body.user_timezone,
            user_local_time=request_body.user_local_time,
            user_time_of_day=request_body.user_time_of_day,
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
            submission, output_text = run_chat_submission(
                request=request,
                gateway=gateway,
                chat_messages=chat_messages,
                instructions=instructions,
                assistant_message_id=assistant_message_id,
                knowledge_references=knowledge_references,
                request_key=request_body.request_key,
                reasoning_session_id=reasoning_session_id,
                reasoning_state=reasoning_state,
            )
        else:
            submission, output_text = run_chat_submission_with_tools(
                request=request,
                gateway=gateway,
                chat_messages=chat_messages,
                instructions=instructions,
                assistant_message_id=assistant_message_id,
                knowledge_references=knowledge_references,
                extra_tools=mcp_registry.tools,
                mcp_registry=mcp_registry,
                request_key=request_body.request_key,
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
            request_key=request_body.request_key,
        )

    @router.post("/chat/resume", response_model_exclude_none=True)
    def resume_chat(
        request_body: ChatResumeRequest,
        request: Request,
        gateway: ChatGateway = Depends(get_chat_gateway),
        state_store: StateStore = Depends(get_state_store),
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
            user_timezone=request_body.user_timezone,
            user_local_time=request_body.user_local_time,
            user_time_of_day=request_body.user_time_of_day,
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

        instructions = f"{instructions}\n\n{build_resume_instruction(request_body.partial_content)}"
        instructions = append_skill_context(
            instructions,
            user_message=request_body.message,
        )
        mcp_registry = build_chat_mcp_registry([])

        chat_started_at = perf_counter()
        submission, output_text = run_chat_submission_with_tools(
            request=request,
            gateway=gateway,
            chat_messages=prepared_context.chat_messages,
            instructions=instructions,
            assistant_message_id=request_body.assistant_message_id,
            initial_output_text=request_body.partial_content,
            knowledge_references=knowledge_references,
            extra_tools=mcp_registry.tools,
            mcp_registry=mcp_registry,
            request_key=request_body.request_key,
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
            request_key=request_body.request_key,
        )

    return router
