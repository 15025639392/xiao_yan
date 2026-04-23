from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.api.deps import (
    get_chat_gateway,
    get_chat_memory_runtime,
    get_persona_service,
    get_platform_adapter_service,
    get_state_store,
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
)
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

    return router
