from __future__ import annotations

from fastapi import HTTPException, Request

from app.api.platform_route_models import (
    ChatSubmissionPreviewRequest,
    PlatformChatPreviewRequest,
    PlatformDraftPreviewRequest,
    PlatformInternalPreviewRequest,
    XiaohongshuCreatorHomePreviewRequest,
    XiaohongshuLeadCaptureRequest,
    XiaohongshuNotificationPreviewRequest,
    PlatformPreviewRequest,
    XiaohongshuImportFilePreviewRequest,
    XiaohongshuImportPreviewRequest,
)
from app.external_executors.xiaohongshu_mcp_client import XiaohongshuMcpClient
from app.llm.gateway import ChatGateway
from app.memory.chat_memory_runtime import ChatMemoryRuntime
from app.persona.service import PersonaService
from app.platform_adapters.chat_submission_bridge import build_decision_draft_from_chat_submission
from app.platform_adapters.models import PlatformProcessResult
from app.platform_adapters.service import PlatformAdapterService
from app.runtime import StateStore
from app.runtime_ext.runtime_config import RuntimeConfig
from app.usecases.platform_preview import PlatformChatPreviewResult, run_platform_chat_preview
from app.usecases.xiaohongshu_creator_home_capture import capture_xiaohongshu_creator_home_via_browser_organ
from app.usecases.xiaohongshu_lead_capture import capture_xiaohongshu_lead_signals_via_browser_organ
from app.usecases.xiaohongshu_creator_home_preview import build_xiaohongshu_creator_home_preview_items
from app.usecases.xiaohongshu_generate_publish_draft import run_xiaohongshu_creator_home_publish_draft
from app.usecases.xiaohongshu_import_batch import load_xiaohongshu_import_batch
from app.usecases.xiaohongshu_import_preview import build_xiaohongshu_import_envelope
from app.usecases.xiaohongshu_notification_preview import build_xiaohongshu_notification_preview_items
from app.usecases.xiaohongshu_publish_autofill import autofill_xiaohongshu_publish_page
from app.usecases.xiaohongshu_publish_via_mcp import publish_xiaohongshu_image_post_via_mcp
from app.usecases.xiaohongshu_text_image_autofill import autofill_xiaohongshu_text_image_cards


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


def handle_xiaohongshu_import_preview(
    *,
    request_body: XiaohongshuImportPreviewRequest,
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
        lambda: _run_xiaohongshu_import_preview(
            request_body=request_body,
            request=request,
            gateway=gateway,
            state_store=state_store,
            persona_service=persona_service,
            chat_memory_runtime=chat_memory_runtime,
            service=service,
            config=config,
        ),
    )


def handle_xiaohongshu_import_file_preview(
    *,
    request_body: XiaohongshuImportFilePreviewRequest,
    request: Request,
    gateway: ChatGateway,
    state_store: StateStore,
    persona_service: PersonaService,
    chat_memory_runtime: ChatMemoryRuntime,
    service: PlatformAdapterService,
    config: RuntimeConfig,
) -> list[PlatformChatPreviewResult]:
    return _wrap_platform_errors(
        service,
        lambda: _run_xiaohongshu_import_file_preview(
            request_body=request_body,
            request=request,
            gateway=gateway,
            state_store=state_store,
            persona_service=persona_service,
            chat_memory_runtime=chat_memory_runtime,
            service=service,
            config=config,
        ),
    )


def handle_xiaohongshu_notification_preview(
    *,
    request_body: XiaohongshuNotificationPreviewRequest,
    request: Request,
    gateway: ChatGateway,
    state_store: StateStore,
    persona_service: PersonaService,
    chat_memory_runtime: ChatMemoryRuntime,
    service: PlatformAdapterService,
    config: RuntimeConfig,
) -> list[PlatformChatPreviewResult]:
    return _wrap_platform_errors(
        service,
        lambda: _run_xiaohongshu_notification_preview(
            request_body=request_body,
            request=request,
            gateway=gateway,
            state_store=state_store,
            persona_service=persona_service,
            chat_memory_runtime=chat_memory_runtime,
            service=service,
            config=config,
        ),
    )


def handle_xiaohongshu_creator_home_preview(
    *,
    request_body: XiaohongshuCreatorHomePreviewRequest,
    request: Request,
    gateway: ChatGateway,
    state_store: StateStore,
    persona_service: PersonaService,
    chat_memory_runtime: ChatMemoryRuntime,
    service: PlatformAdapterService,
    config: RuntimeConfig,
) -> list[PlatformChatPreviewResult]:
    return _wrap_platform_errors(
        service,
        lambda: _run_xiaohongshu_creator_home_preview(
            request_body=request_body,
            request=request,
            gateway=gateway,
            state_store=state_store,
            persona_service=persona_service,
            chat_memory_runtime=chat_memory_runtime,
            service=service,
            config=config,
        ),
    )


def handle_xiaohongshu_creator_home_capture(
    *,
    service: PlatformAdapterService,
):
    return _wrap_platform_errors(service, capture_xiaohongshu_creator_home_via_browser_organ)


def handle_xiaohongshu_publish_autofill(
    *,
    title: str,
    body: str,
    auto_publish: bool = False,
    publish_selector: str = "",
    service: PlatformAdapterService,
):
    return _wrap_platform_errors(
        service,
        lambda: autofill_xiaohongshu_publish_page(
            title=title, body=body, auto_publish=auto_publish, publish_selector=publish_selector
        ),
    )


def handle_xiaohongshu_text_image_autofill(
    *,
    cards: list[str],
    trigger_generate: bool,
    service: PlatformAdapterService,
):
    return _wrap_platform_errors(
        service,
        lambda: autofill_xiaohongshu_text_image_cards(cards=cards, trigger_generate=trigger_generate),
    )


def handle_xiaohongshu_publish_via_mcp(
    *,
    title: str,
    body: str,
    image_paths: list[str],
    client: XiaohongshuMcpClient,
    service: PlatformAdapterService,
):
    return _wrap_platform_errors(
        service,
        lambda: publish_xiaohongshu_image_post_via_mcp(
            title=title,
            body=body,
            image_paths=image_paths,
            client=client,
        ),
    )


def handle_xiaohongshu_lead_capture(
    *,
    request_body: XiaohongshuLeadCaptureRequest,
    state_store: StateStore,
    service: PlatformAdapterService,
):
    browser_session = state_store.get().browser_session
    session_id = browser_session.session_id if browser_session else ""
    if not session_id:
        def _raise_no_session():
            raise ValueError("browser organ has no active xiaohongshu session")

        return _wrap_platform_errors(service, _raise_no_session)
    return _wrap_platform_errors(
        service,
        lambda: capture_xiaohongshu_lead_signals_via_browser_organ(
            session_id=session_id,
            title_hint=request_body.title_hint,
        ),
    )


def _run_xiaohongshu_import_preview(
    *,
    request_body: XiaohongshuImportPreviewRequest,
    request: Request,
    gateway: ChatGateway,
    state_store: StateStore,
    persona_service: PersonaService,
    chat_memory_runtime: ChatMemoryRuntime,
    service: PlatformAdapterService,
    config: RuntimeConfig,
) -> PlatformChatPreviewResult:
    envelope = build_xiaohongshu_import_envelope(request_body)
    return run_platform_chat_preview(
        request=request,
        platform="xiaohongshu",
        raw_payload=envelope.raw_payload,
        message=envelope.message,
        preferred_kind=envelope.preferred_kind,
        gateway=gateway,
        state_store=state_store,
        persona_service=persona_service,
        chat_memory_runtime=chat_memory_runtime,
        platform_service=service,
        config=config,
    )


def _run_xiaohongshu_import_file_preview(
    *,
    request_body: XiaohongshuImportFilePreviewRequest,
    request: Request,
    gateway: ChatGateway,
    state_store: StateStore,
    persona_service: PersonaService,
    chat_memory_runtime: ChatMemoryRuntime,
    service: PlatformAdapterService,
    config: RuntimeConfig,
) -> list[PlatformChatPreviewResult]:
    batch_items = load_xiaohongshu_import_batch(request_body)
    return [
        _run_xiaohongshu_import_preview(
            request_body=item.request,
            request=request,
            gateway=gateway,
            state_store=state_store,
            persona_service=persona_service,
            chat_memory_runtime=chat_memory_runtime,
            service=service,
            config=config,
        )
        for item in batch_items
    ]


def _run_xiaohongshu_notification_preview(
    *,
    request_body: XiaohongshuNotificationPreviewRequest,
    request: Request,
    gateway: ChatGateway,
    state_store: StateStore,
    persona_service: PersonaService,
    chat_memory_runtime: ChatMemoryRuntime,
    service: PlatformAdapterService,
    config: RuntimeConfig,
) -> list[PlatformChatPreviewResult]:
    preview_items = build_xiaohongshu_notification_preview_items(request_body)
    return [
        _run_xiaohongshu_import_preview(
            request_body=item,
            request=request,
            gateway=gateway,
            state_store=state_store,
            persona_service=persona_service,
            chat_memory_runtime=chat_memory_runtime,
            service=service,
            config=config,
        )
        for item in preview_items
    ]


def _run_xiaohongshu_creator_home_preview(
    *,
    request_body: XiaohongshuCreatorHomePreviewRequest,
    request: Request,
    gateway: ChatGateway,
    state_store: StateStore,
    persona_service: PersonaService,
    chat_memory_runtime: ChatMemoryRuntime,
    service: PlatformAdapterService,
    config: RuntimeConfig,
) -> list[PlatformChatPreviewResult]:
    preview_items = build_xiaohongshu_creator_home_preview_items(request_body)
    return [
        run_xiaohongshu_creator_home_publish_draft(
            opportunity=item,
            request=request,
            gateway=gateway,
            state_store=state_store,
            persona_service=persona_service,
            chat_memory_runtime=chat_memory_runtime,
            platform_service=service,
            config=config,
        )
        for item in preview_items
    ]


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
