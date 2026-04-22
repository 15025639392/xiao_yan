from __future__ import annotations

from fastapi import HTTPException, Request

from app.api.platform_route_models import (
    ChatSubmissionPreviewRequest,
    PlatformChatPreviewRequest,
    PlatformDraftPreviewRequest,
    PlatformInternalPreviewRequest,
    PlatformPreviewRequest,
)
from app.llm.gateway import ChatGateway
from app.memory.chat_memory_runtime import ChatMemoryRuntime
from app.persona.service import PersonaService
from app.platform_adapters.chat_submission_bridge import build_decision_draft_from_chat_submission
from app.platform_adapters.models import PlatformProcessResult
from app.platform_adapters.service import PlatformAdapterService
from app.runtime import StateStore
from app.runtime_ext.runtime_config import RuntimeConfig
from app.usecases.platform_preview import PlatformChatPreviewResult, run_platform_chat_preview


def handle_platform_preview(
    *,
    request_body: PlatformPreviewRequest,
    service: PlatformAdapterService,
) -> PlatformProcessResult:
    return _wrap_platform_errors(
        service,
        lambda: service.process(
            platform=request_body.platform,
            raw_payload=request_body.raw_payload,
            decision=request_body.decision,
        ),
    )


def handle_platform_preview_from_core(
    *,
    request_body: PlatformInternalPreviewRequest,
    service: PlatformAdapterService,
) -> PlatformProcessResult:
    return _wrap_platform_errors(
        service,
        lambda: service.process_internal_decision(
            platform=request_body.platform,
            raw_payload=request_body.raw_payload,
            decision_input=request_body.internal_decision,
        ),
    )


def handle_platform_preview_from_draft(
    *,
    request_body: PlatformDraftPreviewRequest,
    service: PlatformAdapterService,
) -> PlatformProcessResult:
    return _wrap_platform_errors(
        service,
        lambda: service.process_decision_draft(
            platform=request_body.platform,
            raw_payload=request_body.raw_payload,
            decision_draft=request_body.decision_draft,
        ),
    )


def handle_platform_preview_from_chat_submission(
    *,
    request_body: ChatSubmissionPreviewRequest,
    service: PlatformAdapterService,
) -> PlatformProcessResult:
    def _run() -> PlatformProcessResult:
        decision_draft = build_decision_draft_from_chat_submission(
            submission=request_body.submission,
            output_text=request_body.output_text,
            preferred_kind=request_body.preferred_kind,
            summary=request_body.summary,
            supporting_points=request_body.supporting_points,
            metadata=request_body.metadata,
        )
        return service.process_decision_draft(
            platform=request_body.platform,
            raw_payload=request_body.raw_payload,
            decision_draft=decision_draft,
        )

    return _wrap_platform_errors(service, _run)


def handle_platform_preview_with_chat(
    *,
    request_body: PlatformChatPreviewRequest,
    request: Request,
    gateway: ChatGateway,
    state_store: StateStore,
    persona_service: PersonaService,
    chat_memory_runtime: ChatMemoryRuntime,
    service: PlatformAdapterService,
    config: RuntimeConfig,
) -> PlatformChatPreviewResult:
    return _wrap_platform_errors(
        service,
        lambda: run_platform_chat_preview(
            request=request,
            platform=request_body.platform,
            raw_payload=request_body.raw_payload,
            message=request_body.message,
            preferred_kind=request_body.preferred_kind,
            gateway=gateway,
            state_store=state_store,
            persona_service=persona_service,
            chat_memory_runtime=chat_memory_runtime,
            platform_service=service,
            config=config,
        ),
    )


def _wrap_platform_errors(service: PlatformAdapterService, fn):
    try:
        return fn()
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail={
                "message": str(exc),
                "supported_platforms": service.list_platforms(),
            },
        ) from exc
