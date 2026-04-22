from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable


@dataclass(frozen=True)
class XiaohongshuDraftGenerationOutcome:
    draft: dict[str, Any]
    action_title: str
    action_data: dict[str, Any]


def build_xiaohongshu_opportunity_items(last_scouting_data: dict[str, Any]) -> list[dict[str, str]]:
    topics = last_scouting_data.get("topics", [])
    activities = last_scouting_data.get("activities", [])

    items: list[dict[str, str]] = []
    for topic in topics[:5]:
        items.append(
            {
                "source_kind": "topic",
                "title": topic.get("topic", ""),
                "summary": f"参与人数: {topic.get('participation_count', '未知')}",
            }
        )
    for activity in activities[:3]:
        items.append(
            {
                "source_kind": "activity",
                "title": activity.get("title", ""),
                "summary": activity.get("date_range", "") + " " + (activity.get("incentive_hint") or ""),
            }
        )
    return items


def generate_xiaohongshu_draft_from_opportunity(
    opportunity: dict[str, str],
    *,
    gateway: Any,
    build_prompt: Callable[[dict[str, str]], str],
) -> XiaohongshuDraftGenerationOutcome:
    generated_title = ""
    generated_body = ""

    if gateway is not None:
        prompt = build_prompt(opportunity)
        try:
            from app.llm.schemas import ChatMessage

            messages = [ChatMessage(role="user", content=prompt)]
            result = gateway.create_response(
                messages,
                instructions="你是一个小红书内容创作专家，直接输出标题和正文，不要其他解释。",
            )
            output_text = result.output_text or ""
            generated_title, generated_body = _parse_generated_title_and_body(output_text)
            if not generated_title:
                generated_title = f"探索 {opportunity['title'][:15]} 的创作灵感"
                generated_body = output_text[:500] if output_text else f"根据最新侦察结果生成的内容草稿：{opportunity['title']}"
        except Exception:
            generated_title = ""
            generated_body = ""

    if not generated_title:
        generated_title = f"探索 {opportunity['title'][:20]} 的创作灵感"
        generated_body = f"根据最新侦察结果生成的内容草稿：{opportunity['title']}。{opportunity.get('summary', '')}"

    draft_id = str(uuid.uuid4())[:8]
    draft = {
        "draft_id": draft_id,
        "title": generated_title,
        "body": generated_body,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "pending",
        "source_kind": opportunity.get("source_kind", "topic"),
        "opportunity_title": opportunity.get("title", ""),
    }
    return XiaohongshuDraftGenerationOutcome(
        draft=draft,
        action_title=f"草稿生成：{generated_title[:20]}",
        action_data={"draft_id": draft_id, "title": generated_title},
    )


def _parse_generated_title_and_body(output_text: str) -> tuple[str, str]:
    if "标题：" not in output_text:
        return "", ""

    parts = output_text.split("标题：", 1)
    if len(parts) <= 1:
        return "", ""

    title_and_body = parts[1]
    if "正文：" in title_and_body:
        title_parts = title_and_body.split("正文：", 1)
        return title_parts[0].strip(), title_parts[1].strip()
    return title_and_body.strip(), ""
