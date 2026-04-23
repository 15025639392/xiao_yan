from __future__ import annotations

import re

from fastapi import Request

from app.api.chat_route_context import prepare_route_chat_context
from app.api.chat_submission_runner import run_chat_submission_with_tools
from app.api.platform_route_models import (
    XiaohongshuImageCardDraftItem,
    XiaohongshuStructuredPublishDraft,
)
from app.llm.gateway import ChatGateway
from app.llm.schemas import ChatRequest
from app.memory.chat_memory_runtime import ChatMemoryRuntime
from app.persona.service import PersonaService
from app.runtime import StateStore
from app.runtime_ext.runtime_config import RuntimeConfig
from app.usecases.platform_preview import PlatformChatPreviewResult
from app.usecases.xiaohongshu_content_strategy import (
    build_xiaohongshu_creator_home_prompt as build_creator_home_publish_prompt,
    collapse_xiaohongshu_body_sections,
    normalize_xiaohongshu_body,
    normalize_xiaohongshu_title,
)
from app.usecases.xiaohongshu_creator_home_preview import XiaohongshuCreatorOpportunityItem


def run_xiaohongshu_creator_home_publish_draft(
    *,
    opportunity: XiaohongshuCreatorOpportunityItem,
    request: Request,
    gateway: ChatGateway,
    state_store: StateStore,
    persona_service: PersonaService,
    chat_memory_runtime: ChatMemoryRuntime,
    platform_service,
    config: RuntimeConfig,
) -> PlatformChatPreviewResult:
    prompt = build_xiaohongshu_creator_home_prompt(opportunity)
    request_body = ChatRequest(message=prompt)
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
        assistant_message_id="xiaohongshu_creator_home_assistant",
        memory_references=route_context.memory_references,
        request_key=None,
    )
    publish_draft = parse_xiaohongshu_publish_draft(
        output_text=output_text,
        source_title=opportunity.title,
        source_summary=opportunity.summary,
    )
    platform_result = platform_service.process_decision_draft(
        platform="xiaohongshu",
        raw_payload=opportunity.request.note.model_dump(mode="json") if opportunity.request.note is not None else {},
        decision_draft={
            "kind": "note_draft",
            "text": render_publish_draft_as_text(publish_draft),
            "assistant_message_id": submission.assistant_message_id,
            "reasoning_session_id": submission.reasoning_session_id,
            "metadata": {"source_route": "xiaohongshu_creator_home_preview"},
        },
    )
    lead_assessment = None
    if platform_result.event.platform == "xiaohongshu":
        from app.usecases.xiaohongshu_lead_assessment import assess_xiaohongshu_lead

        lead_assessment = assess_xiaohongshu_lead(platform_result.event)
    return PlatformChatPreviewResult(
        submission=submission,
        output_text=output_text,
        platform_result=platform_result,
        lead_assessment=lead_assessment,
        publish_draft=publish_draft,
    )


def build_xiaohongshu_creator_home_prompt(opportunity: XiaohongshuCreatorOpportunityItem) -> str:
    return build_creator_home_publish_prompt(
        source_kind=opportunity.source_kind,
        source_title=opportunity.title,
        source_summary=opportunity.summary,
        raw_material=opportunity.request.note.note_text if opportunity.request.note is not None else "",
    )


def parse_xiaohongshu_publish_draft(
    *,
    output_text: str,
    source_title: str,
    source_summary: str | None = None,
) -> XiaohongshuStructuredPublishDraft:
    title = _extract_section(output_text, "标题") or _fallback_title(source_title)
    opening = _extract_section(output_text, "开头") or f"今天刷到 {source_title}，我先想到的不是跟风，而是这条内容到底能帮谁解决一个具体问题。"
    body_block = _extract_section(output_text, "正文")
    body_sections = _normalize_bullets(body_block) or [
        line
        for line in [
            f"先把 {source_title} 放进一个具体场景里，而不是只讲概念。",
            "正文别铺太满，直接讲一个最容易照着做的动作。",
            source_summary or "结尾留一个轻互动，让真正有兴趣的人愿意继续问。",
        ]
        if line
    ]
    closing_cta = _extract_section(output_text, "结尾") or "如果你也在做这一类内容，可以直接从最具体的那一个场景开始写。"
    first_comment = _extract_section(output_text, "首评") or "如果你愿意，小晏可以继续陪你慢慢看这件事。"
    image_cards = _extract_image_cards(output_text, title=title, opening=opening, body_sections=body_sections, closing_cta=closing_cta)
    normalized_body_sections = collapse_xiaohongshu_body_sections(body_sections)
    return XiaohongshuStructuredPublishDraft(
        title=normalize_xiaohongshu_title(title, fallback=_fallback_title(source_title)),
        opening=normalize_xiaohongshu_body(opening),
        body_sections=normalized_body_sections,
        closing_cta=normalize_xiaohongshu_body(closing_cta),
        first_comment=normalize_xiaohongshu_body(first_comment),
        image_cards=image_cards,
    )


def render_publish_draft_as_text(draft: XiaohongshuStructuredPublishDraft) -> str:
    body = "\n\n".join([draft.opening, *draft.body_sections, draft.closing_cta]).strip()
    return f"标题：{draft.title}\n\n正文：\n{body}"


def _extract_section(output_text: str, name: str) -> str | None:
    pattern = re.compile(rf"【{re.escape(name)}】\s*(.*?)(?=\n【[^】]+】|\Z)", re.S)
    match = pattern.search(output_text)
    if not match:
        return None
    value = match.group(1).strip()
    return value or None


def _normalize_bullets(value: str | None) -> list[str]:
    if not value:
        return []
    lines = []
    for raw in value.splitlines():
        text = raw.strip()
        if not text:
            continue
        text = re.sub(r"^[-*•\d\.\s]+", "", text).strip()
        if text:
            lines.append(text)
    return lines


def _extract_image_cards(
    output_text: str,
    *,
    title: str,
    opening: str,
    body_sections: list[str],
    closing_cta: str,
) -> list[XiaohongshuImageCardDraftItem]:
    cards: list[XiaohongshuImageCardDraftItem] = []
    for index in range(1, 4):
        block = _extract_section(output_text, f"图卡{index}")
        if not block:
            continue
        card_title = None
        card_body = None
        for line in block.splitlines():
            text = line.strip()
            if text.startswith("标题："):
                card_title = normalize_xiaohongshu_title(text.removeprefix("标题：").strip(), fallback=title)
            elif text.startswith("内容："):
                card_body = normalize_xiaohongshu_body(text.removeprefix("内容：").strip())
        if card_title and card_body:
            cards.append(XiaohongshuImageCardDraftItem(title=card_title, body=card_body))
    if cards:
        return cards
    fallback_bodies = [
        opening,
        "\n".join(body_sections[:2]).strip(),
        closing_cta,
    ]
    fallback_titles = [title, "怎么写更容易被看完", "结尾怎么把人留下来"]
    return [
        XiaohongshuImageCardDraftItem(title=fallback_titles[idx], body=fallback_bodies[idx] or fallback_titles[idx])
        for idx in range(3)
    ]


def _fallback_title(source_title: str) -> str:
    normalized = source_title.strip()
    if not normalized:
        return "小晏先讲这个瞬间"
    if normalized.startswith("#"):
        return normalize_xiaohongshu_title(f"{normalized}：小晏先讲这个瞬间", fallback="小晏先讲这个瞬间")
    return normalize_xiaohongshu_title(f"{normalized}：小晏慢慢讲清楚", fallback="小晏先讲这个瞬间")
