from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.api.deps import (
    get_chat_gateway,
    get_chat_memory_runtime,
    get_persona_service,
    get_platform_adapter_service,
    get_state_store,
    get_xiaohongshu_mcp_client,
)
from app.api.platform_handlers_core import (
    handle_platform_preview,
    handle_platform_preview_from_chat_submission,
    handle_platform_preview_from_core,
    handle_platform_preview_from_draft,
    handle_platform_preview_with_chat,
)
from app.api.xiaohongshu_handlers import (
    handle_xiaohongshu_cover_preview,
    handle_xiaohongshu_creator_home_capture,
    handle_xiaohongshu_creator_home_preview,
    handle_xiaohongshu_import_file_preview,
    handle_xiaohongshu_import_preview,
    handle_xiaohongshu_lead_capture,
    handle_xiaohongshu_notification_preview,
    handle_xiaohongshu_publish_autofill,
    handle_xiaohongshu_publish_via_mcp,
    handle_xiaohongshu_text_image_autofill,
)
from app.api.platform_route_models import (
    ChatSubmissionPreviewRequest,
    PlatformChatPreviewRequest,
    PlatformDraftPreviewRequest,
    PlatformInternalPreviewRequest,
    PlatformListResponse,
    PlatformPreviewRequest,
    XiaohongshuCoverPreviewRequest,
    XiaohongshuCoverPreviewResponse,
    XiaohongshuCreatorHomeCaptureResponse,
    XiaohongshuCreatorHomePreviewRequest,
    XiaohongshuImportFilePreviewRequest,
    XiaohongshuImportPreviewRequest,
    XiaohongshuLeadCaptureRequest,
    XiaohongshuLeadCaptureResponse,
    XiaohongshuNotificationPreviewRequest,
    XiaohongshuPublishAutofillRequest,
    XiaohongshuPublishAutofillResponse,
    XiaohongshuPublishViaMcpRequest,
    XiaohongshuPublishViaMcpResponse,
    XiaohongshuTextImageAutofillRequest,
    XiaohongshuTextImageAutofillResponse,
)
from app.external_executors.xiaohongshu_mcp_client import XiaohongshuMcpClient
from app.llm.gateway import ChatGateway
from app.memory.chat_memory_runtime import ChatMemoryRuntime
from app.persona.service import PersonaService
from app.platform_adapters.models import PlatformProcessResult
from app.platform_adapters.service import PlatformAdapterService
from app.runtime import StateStore
from app.runtime_ext.runtime_config import get_runtime_config
from app.usecases.platform_preview import PlatformChatPreviewResult


def build_platform_router() -> APIRouter:
    router = APIRouter(prefix="/platform-adapters", tags=["platform-adapters"])

    @router.get("")
    def list_platform_adapters(
        service: PlatformAdapterService = Depends(get_platform_adapter_service),
    ) -> PlatformListResponse:
        return PlatformListResponse(platforms=service.list_platforms())

    @router.post("/preview", response_model=PlatformProcessResult)
    def preview_platform_adaptation(
        request_body: PlatformPreviewRequest,
        service: PlatformAdapterService = Depends(get_platform_adapter_service),
    ) -> PlatformProcessResult:
        return handle_platform_preview(request_body=request_body, service=service)

    @router.post("/preview-from-core", response_model=PlatformProcessResult)
    def preview_platform_adaptation_from_core(
        request_body: PlatformInternalPreviewRequest,
        service: PlatformAdapterService = Depends(get_platform_adapter_service),
    ) -> PlatformProcessResult:
        return handle_platform_preview_from_core(request_body=request_body, service=service)

    @router.post("/preview-from-draft", response_model=PlatformProcessResult)
    def preview_platform_adaptation_from_draft(
        request_body: PlatformDraftPreviewRequest,
        service: PlatformAdapterService = Depends(get_platform_adapter_service),
    ) -> PlatformProcessResult:
        return handle_platform_preview_from_draft(request_body=request_body, service=service)

    @router.post("/preview-from-chat-submission", response_model=PlatformProcessResult)
    def preview_platform_adaptation_from_chat_submission(
        request_body: ChatSubmissionPreviewRequest,
        service: PlatformAdapterService = Depends(get_platform_adapter_service),
    ) -> PlatformProcessResult:
        return handle_platform_preview_from_chat_submission(request_body=request_body, service=service)

    @router.post("/preview-with-chat", response_model=PlatformChatPreviewResult)
    def preview_platform_adaptation_with_chat(
        request_body: PlatformChatPreviewRequest,
        request: Request,
        gateway: ChatGateway = Depends(get_chat_gateway),
        state_store: StateStore = Depends(get_state_store),
        persona_service: PersonaService = Depends(get_persona_service),
        chat_memory_runtime: ChatMemoryRuntime = Depends(get_chat_memory_runtime),
        service: PlatformAdapterService = Depends(get_platform_adapter_service),
    ) -> PlatformChatPreviewResult:
        return handle_platform_preview_with_chat(
            request_body=request_body,
            request=request,
            gateway=gateway,
            state_store=state_store,
            persona_service=persona_service,
            chat_memory_runtime=chat_memory_runtime,
            service=service,
            config=get_runtime_config(),
        )

    @router.post("/xiaohongshu/import-preview", response_model=PlatformChatPreviewResult)
    def preview_xiaohongshu_import(
        request_body: XiaohongshuImportPreviewRequest,
        request: Request,
        gateway: ChatGateway = Depends(get_chat_gateway),
        state_store: StateStore = Depends(get_state_store),
        persona_service: PersonaService = Depends(get_persona_service),
        chat_memory_runtime: ChatMemoryRuntime = Depends(get_chat_memory_runtime),
        service: PlatformAdapterService = Depends(get_platform_adapter_service),
    ) -> PlatformChatPreviewResult:
        return handle_xiaohongshu_import_preview(
            request_body=request_body,
            request=request,
            gateway=gateway,
            state_store=state_store,
            persona_service=persona_service,
            chat_memory_runtime=chat_memory_runtime,
            service=service,
            config=get_runtime_config(),
        )

    @router.post("/xiaohongshu/import-preview-file", response_model=list[PlatformChatPreviewResult])
    def preview_xiaohongshu_import_file(
        request_body: XiaohongshuImportFilePreviewRequest,
        request: Request,
        gateway: ChatGateway = Depends(get_chat_gateway),
        state_store: StateStore = Depends(get_state_store),
        persona_service: PersonaService = Depends(get_persona_service),
        chat_memory_runtime: ChatMemoryRuntime = Depends(get_chat_memory_runtime),
        service: PlatformAdapterService = Depends(get_platform_adapter_service),
    ) -> list[PlatformChatPreviewResult]:
        return handle_xiaohongshu_import_file_preview(
            request_body=request_body,
            request=request,
            gateway=gateway,
            state_store=state_store,
            persona_service=persona_service,
            chat_memory_runtime=chat_memory_runtime,
            service=service,
            config=get_runtime_config(),
        )

    @router.post("/xiaohongshu/notification-preview", response_model=list[PlatformChatPreviewResult])
    def preview_xiaohongshu_notification_page(
        request_body: XiaohongshuNotificationPreviewRequest,
        request: Request,
        gateway: ChatGateway = Depends(get_chat_gateway),
        state_store: StateStore = Depends(get_state_store),
        persona_service: PersonaService = Depends(get_persona_service),
        chat_memory_runtime: ChatMemoryRuntime = Depends(get_chat_memory_runtime),
        service: PlatformAdapterService = Depends(get_platform_adapter_service),
    ) -> list[PlatformChatPreviewResult]:
        return handle_xiaohongshu_notification_preview(
            request_body=request_body,
            request=request,
            gateway=gateway,
            state_store=state_store,
            persona_service=persona_service,
            chat_memory_runtime=chat_memory_runtime,
            service=service,
            config=get_runtime_config(),
        )

    @router.post("/xiaohongshu/creator-home-preview", response_model=list[PlatformChatPreviewResult])
    def preview_xiaohongshu_creator_home(
        request_body: XiaohongshuCreatorHomePreviewRequest,
        request: Request,
        gateway: ChatGateway = Depends(get_chat_gateway),
        state_store: StateStore = Depends(get_state_store),
        persona_service: PersonaService = Depends(get_persona_service),
        chat_memory_runtime: ChatMemoryRuntime = Depends(get_chat_memory_runtime),
        service: PlatformAdapterService = Depends(get_platform_adapter_service),
    ) -> list[PlatformChatPreviewResult]:
        return handle_xiaohongshu_creator_home_preview(
            request_body=request_body,
            request=request,
            gateway=gateway,
            state_store=state_store,
            persona_service=persona_service,
            chat_memory_runtime=chat_memory_runtime,
            service=service,
            config=get_runtime_config(),
        )

    @router.post("/xiaohongshu/creator-home-capture", response_model=XiaohongshuCreatorHomeCaptureResponse)
    def capture_xiaohongshu_creator_home(
        service: PlatformAdapterService = Depends(get_platform_adapter_service),
    ) -> XiaohongshuCreatorHomeCaptureResponse:
        return handle_xiaohongshu_creator_home_capture(service=service)

    @router.post("/xiaohongshu/publish-autofill", response_model=XiaohongshuPublishAutofillResponse)
    def autofill_xiaohongshu_publish_page(
        request_body: XiaohongshuPublishAutofillRequest,
        service: PlatformAdapterService = Depends(get_platform_adapter_service),
    ) -> XiaohongshuPublishAutofillResponse:
        return handle_xiaohongshu_publish_autofill(
            title=request_body.title,
            body=request_body.body,
            auto_publish=request_body.auto_publish,
            publish_selector=request_body.publish_selector,
            service=service,
        )

    @router.post("/xiaohongshu/publish-via-mcp", response_model=XiaohongshuPublishViaMcpResponse)
    def publish_xiaohongshu_via_mcp_route(
        request_body: XiaohongshuPublishViaMcpRequest,
        service: PlatformAdapterService = Depends(get_platform_adapter_service),
        client: XiaohongshuMcpClient = Depends(get_xiaohongshu_mcp_client),
    ) -> XiaohongshuPublishViaMcpResponse:
        return handle_xiaohongshu_publish_via_mcp(
            title=request_body.title,
            body=request_body.body,
            image_paths=request_body.image_paths,
            client=client,
            service=service,
        )

    @router.post("/xiaohongshu/cover-preview", response_model=XiaohongshuCoverPreviewResponse)
    def preview_xiaohongshu_cover_route(
        request_body: XiaohongshuCoverPreviewRequest,
        service: PlatformAdapterService = Depends(get_platform_adapter_service),
    ) -> XiaohongshuCoverPreviewResponse:
        return handle_xiaohongshu_cover_preview(
            title=request_body.title,
            body=request_body.body,
            template_name=request_body.template_name,
            service=service,
        )

    @router.post("/xiaohongshu/text-image-autofill", response_model=XiaohongshuTextImageAutofillResponse)
    def autofill_xiaohongshu_text_image_cards_route(
        request_body: XiaohongshuTextImageAutofillRequest,
        service: PlatformAdapterService = Depends(get_platform_adapter_service),
    ) -> XiaohongshuTextImageAutofillResponse:
        return handle_xiaohongshu_text_image_autofill(
            cards=request_body.cards,
            trigger_generate=request_body.trigger_generate,
            service=service,
        )

    @router.post("/xiaohongshu/lead-capture", response_model=XiaohongshuLeadCaptureResponse)
    def capture_xiaohongshu_lead_route(
        request_body: XiaohongshuLeadCaptureRequest,
        state_store: StateStore = Depends(get_state_store),
        service: PlatformAdapterService = Depends(get_platform_adapter_service),
    ) -> XiaohongshuLeadCaptureResponse:
        return handle_xiaohongshu_lead_capture(
            request_body=request_body,
            state_store=state_store,
            service=service,
        )

    return router
