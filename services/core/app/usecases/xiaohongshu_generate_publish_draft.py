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
    return (
        "你现在不是在写运营建议，也不是在写方法论说明，而是在直接写一篇可以人工确认后发布的小红书图文稿。\n"
        "要求：\n"
        "1. 语言像真人发笔记，少抽象词，少空话。\n"
        "2. 必须写出一个明确场景、一个明确问题、一个明确动作。\n"
        "3. 禁止出现“最小闭环”“验证反馈”“轻量转化”“先跑通”这类产品黑话。\n"
        "4. 不要写成课程大纲，不要写成写作指导。\n"
        "5. 输出必须严格使用下面格式。\n\n"
        f"机会来源：{opportunity.source_kind}\n"
        f"机会标题：{opportunity.title}\n"
        f"补充信息：{opportunity.summary or '无'}\n"
        f"原始素材：{opportunity.request.note.note_text if opportunity.request.note is not None else ''}\n\n"
        "请严格输出：\n"
        "【标题】\n"
        "...\n"
        "【开头】\n"
        "...\n"
        "【正文】\n"
        "- ...\n"
        "- ...\n"
        "- ...\n"
        "【结尾】\n"
        "...\n"
        "【首评】\n"
        "...\n"
        "【图卡1】\n"
        "标题：...\n"
        "内容：...\n"
        "【图卡2】\n"
        "标题：...\n"
        "内容：...\n"
        "【图卡3】\n"
        "标题：...\n"
        "内容：..."
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
    first_comment = _extract_section(output_text, "首评") or "如果你想看我把这条拆成更具体的标题和配图版本，可以留言，我继续补。"
    image_cards = _extract_image_cards(output_text, title=title, opening=opening, body_sections=body_sections, closing_cta=closing_cta)
    return XiaohongshuStructuredPublishDraft(
        title=title.strip(),
        opening=opening.strip(),
        body_sections=[section.strip() for section in body_sections if section.strip()],
        closing_cta=closing_cta.strip(),
        first_comment=first_comment.strip(),
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
                card_title = text.removeprefix("标题：").strip()
            elif text.startswith("内容："):
                card_body = text.removeprefix("内容：").strip()
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
        return "这条内容我会这样写"
    if normalized.startswith("#"):
        return f"{normalized} 这个话题，别再空讲了，直接这样写"
    return f"{normalized} 这件事，我会先这样发第一条"
