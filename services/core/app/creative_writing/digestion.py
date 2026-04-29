from __future__ import annotations

import json

from app.creative_writing.models import NovelFragmentDigest, NovelProject, NovelWritingContext
from app.llm.gateway import ChatGateway
from app.llm.schemas import ChatMessage


def digest_fragment(
    *,
    gateway: ChatGateway | None,
    project: NovelProject,
    content: str,
    intention: str | None,
    context: NovelWritingContext,
) -> NovelFragmentDigest | None:
    if gateway is None:
        return None
    result = gateway.create_response(
        [ChatMessage(role="user", content=build_digest_prompt(project, content, intention, context))],
        instructions=build_digest_instructions(),
    )
    payload = _parse_json_object(result.output_text)
    if payload is None:
        return None
    return NovelFragmentDigest.model_validate(
        {
            "summary": str(payload.get("summary", "")).strip(),
            "next_intention": str(payload.get("next_intention", "")).strip(),
            "should_advance_chapter": bool(payload.get("should_advance_chapter", False)),
            "chapter_closure_reason": str(payload.get("chapter_closure_reason", "")).strip(),
        }
    )


def build_digest_instructions() -> str:
    return (
        "你是小晏的小说创作消化器。只输出 JSON 对象，不要解释。"
        "字段：summary, next_intention, should_advance_chapter, chapter_closure_reason。"
    )


def build_digest_prompt(
    project: NovelProject,
    content: str,
    intention: str | None,
    context: NovelWritingContext,
) -> str:
    return (
        f"小说标题：{project.title}\n"
        f"当前章节：第 {context.chapter_index} 章\n"
        f"本次写作意图：{intention or '未指定'}\n"
        f"前章摘要：{context.previous_chapter_summaries or []}\n"
        f"近期摘要：{context.recent_summaries or []}\n\n"
        f"本次新增正文：\n{content}\n\n"
        "请生成：\n"
        "- summary：一句到三句片段摘要\n"
        "- next_intention：下一次最自然想写的动作或场景\n"
        "- should_advance_chapter：如果本章情绪/事件已经明显收束则为 true\n"
        "- chapter_closure_reason：建议收章的原因；不建议则留空"
    )


def _parse_json_object(text: str) -> dict | None:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`")
        if stripped.startswith("json"):
            stripped = stripped[4:].strip()
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start < 0 or end < start:
        return None
    try:
        parsed = json.loads(stripped[start : end + 1])
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None
