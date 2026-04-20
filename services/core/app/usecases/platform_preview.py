from __future__ import annotations

from pydantic import BaseModel

from app.api.chat_route_context import prepare_route_chat_context
from app.api.chat_submission_runner import run_chat_submission_with_tools
from app.llm.gateway import ChatGateway
from app.llm.schemas import ChatRequest, ChatSubmissionResult
from app.memory.chat_memory_runtime import ChatMemoryRuntime
from app.persona.service import PersonaService
from app.platform_adapters.chat_submission_bridge import build_decision_draft_from_chat_submission
from app.platform_adapters.models import CoreDecisionKind, LeadAssessment, PlatformProcessResult
from app.platform_adapters.service import PlatformAdapterService
from app.runtime import StateStore
from app.runtime_ext.runtime_config import RuntimeConfig
from app.usecases.xiaohongshu_lead_assessment import assess_xiaohongshu_lead
from fastapi import Request


class PlatformChatPreviewResult(BaseModel):
    submission: ChatSubmissionResult
    output_text: str
    platform_result: PlatformProcessResult
    lead_assessment: LeadAssessment | None = None
    publish_draft: object | None = None


def run_platform_chat_preview(
    *,
    request: Request,
    platform: str,
    raw_payload: dict,
    message: str | None,
    preferred_kind: CoreDecisionKind | None,
    gateway: ChatGateway,
    state_store: StateStore,
    persona_service: PersonaService,
    chat_memory_runtime: ChatMemoryRuntime,
    platform_service: PlatformAdapterService,
    config: RuntimeConfig,
) -> PlatformChatPreviewResult:
    event = platform_service.parse_event(platform=platform, raw_payload=raw_payload)
    preview_message = build_platform_preview_message(
        platform=platform,
        event_text=event.text,
        user_message=message,
    )
    request_body = ChatRequest(message=preview_message)
    route_context = prepare_route_chat_context(
        request=request,
        request_body=request_body,
        gateway=gateway,
        state_store=state_store,
        persona_service=persona_service,
        chat_memory_runtime=chat_memory_runtime,
        config=config,
    )
    submission, output_text = run_chat_submission_with_tools(
        request=request,
        gateway=gateway,
        chat_messages=route_context.chat_messages,
        instructions=route_context.instructions,
        assistant_message_id="platform_preview_assistant",
        memory_references=route_context.memory_references,
        request_key=None,
    )
    decision_draft = build_decision_draft_from_chat_submission(
        submission=submission,
        output_text=output_text,
        preferred_kind=preferred_kind,
        metadata={"source_route": "platform_preview"},
    )
    platform_result = platform_service.process_decision_draft(
        platform=platform,
        raw_payload=raw_payload,
        decision_draft=decision_draft,
    )
    lead_assessment = _build_lead_assessment(platform=platform, platform_result=platform_result)
    return PlatformChatPreviewResult(
        submission=submission,
        output_text=output_text,
        platform_result=platform_result,
        lead_assessment=lead_assessment,
    )


def build_platform_preview_message(
    *,
    platform: str,
    event_text: str,
    user_message: str | None,
) -> str:
    normalized_message = (user_message or "").strip()
    if normalized_message:
        return normalized_message
    normalized_event = (event_text or "").strip()
    if normalized_event:
        return (
            f"这是一个来自{platform}的平台事件，请先理解上下文，再给出一条可直接使用的回复建议或草稿：\n"
            f"{normalized_event}"
        )
    return f"这是一个来自{platform}的平台事件，请给出一条可直接使用的回复建议或草稿。"


def _build_lead_assessment(
    *,
    platform: str,
    platform_result: PlatformProcessResult,
) -> LeadAssessment | None:
    if platform != "xiaohongshu":
        return None
    return assess_xiaohongshu_lead(platform_result.event)
