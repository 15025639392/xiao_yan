from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter

from fastapi import Request

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
    extract_memory_references,
    prepare_chat_context,
    record_retrieval_observability,
)
from app.api.chat_runtime_helpers import get_observability_tracker
from app.api.chat_skills import append_skill_context
from app.llm.gateway import ChatGateway
from app.llm.schemas import ChatMessage
from app.memory.chat_memory_runtime import ChatMemoryRuntime
from app.persona.service import PersonaService
from app.runtime import StateStore
from app.runtime_ext.runtime_config import RuntimeConfig


@dataclass(slots=True)
class PreparedRouteChatContext:
    prepared_context: object
    tracker: object | None
    memory_references: list[dict[str, str | float | None]]
    instructions: str
    chat_messages: list[ChatMessage]
    attached_folder_paths: list[str]
    attached_file_paths: list[str]
    attached_image_paths: list[str]
    effective_user_message: str


def prepare_route_chat_context(
    *,
    request: Request,
    request_body,
    gateway: ChatGateway,
    state_store: StateStore,
    persona_service: PersonaService,
    chat_memory_runtime: ChatMemoryRuntime,
    config: RuntimeConfig,
) -> PreparedRouteChatContext:
    state = state_store.get()
    gateway.model = config.chat_model
    prepared_context = prepare_chat_context(
        chat_memory_runtime=chat_memory_runtime,
        context_limit=config.chat_context_limit,
        persona_service=persona_service,
        state=state,
        user_message=request_body.message,
    )
    attached_folder_paths = resolve_attachment_paths(getattr(request_body, "attachments", None), "folder")
    attached_file_paths = resolve_attachment_paths(getattr(request_body, "attachments", None), "file")
    attached_image_paths = resolve_attachment_paths(getattr(request_body, "attachments", None), "image")

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
    memory_references = extract_memory_references(prepared_context.memory_context)
    if prepared_context.retrieval_attempted:
        record_retrieval_observability(
            tracker=tracker,
            latency_ms=(perf_counter() - retrieval_started_at) * 1000.0,
            references=memory_references,
            failed=prepared_context.retrieval_failed,
        )

    user_content, image_parts = build_user_content(
        attachments=getattr(request_body, "attachments", None),
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
        requested_skills=getattr(request_body, "skills", None),
    )
    return PreparedRouteChatContext(
        prepared_context=prepared_context,
        tracker=tracker,
        memory_references=memory_references,
        instructions=instructions,
        chat_messages=chat_messages,
        attached_folder_paths=attached_folder_paths,
        attached_file_paths=attached_file_paths,
        attached_image_paths=attached_image_paths,
        effective_user_message=effective_user_message,
    )


def prepare_route_resume_context(
    *,
    request: Request,
    request_body,
    gateway: ChatGateway,
    state_store: StateStore,
    persona_service: PersonaService,
    chat_memory_runtime: ChatMemoryRuntime,
    config: RuntimeConfig,
) -> PreparedRouteChatContext:
    state = state_store.get()
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
    memory_references = extract_memory_references(prepared_context.memory_context)
    if prepared_context.retrieval_attempted:
        record_retrieval_observability(
            tracker=tracker,
            latency_ms=(perf_counter() - retrieval_started_at) * 1000.0,
            references=memory_references,
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
    instructions = append_skill_context(instructions, user_message=request_body.message)
    return PreparedRouteChatContext(
        prepared_context=prepared_context,
        tracker=tracker,
        memory_references=memory_references,
        instructions=instructions,
        chat_messages=prepared_context.chat_messages,
        attached_folder_paths=[],
        attached_file_paths=[],
        attached_image_paths=[],
        effective_user_message=request_body.message,
    )
