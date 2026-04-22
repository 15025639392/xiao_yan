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


def _parse_count(value: str | None) -> float:
    """Parse '1.2万' / '1.2w' → 12000.0, plain digits → int."""
    if value is None:
        return 0.0
    v = str(value).strip()
    multiplier = 1.0
    if v.endswith(("万", "w", "W")):
        v = v[:-1]
        multiplier = 10000.0
    try:
        return float(v) * multiplier
    except ValueError:
        return 0.0


def build_xiaohongshu_opportunity_items(
    last_scouting_data: dict[str, Any],
    published_history: list[dict[str, Any]] | None = None,
    recent_topics: list[str] | None = None,
) -> list[dict[str, str]]:
    """Build ranked opportunity items from scouting data.

    Ranking signals:
    1. Past engagement on this topic (from published_history metrics)
    2. Activity entries (always included, ranked after top topics)
    3. Topic popularity (participation + view count from page)

    Topics already in recent_topics are deprioritized to the bottom.
    """
    topics = last_scouting_data.get("topics", [])
    activities = last_scouting_data.get("activities", [])
    history = published_history or []
    recent = set(recent_topics or [])

    # Build engagement lookup: opportunity_title → total_engagement
    engagement: dict[str, float] = {}
    for entry in history:
        m = entry.get("metrics") or {}
        score = _parse_count(m.get("like_count")) + _parse_count(m.get("collect_count")) + _parse_count(m.get("comment_count"))
        opp_title = entry.get("opportunity_title", "")
        if opp_title:
            engagement[opp_title] = engagement.get(opp_title, 0.0) + score

    def topic_score(t: dict) -> float:
        title = t.get("topic", "")
        if title in recent:
            return -1.0  # deprioritize recently used
        return engagement.get(title, 0.0)

    # Sort: high-engagement first, recently-used topics last, keep top 5
    sorted_topics = sorted(topics, key=topic_score, reverse=True)[:5]

    items: list[dict[str, str]] = []
    for topic in sorted_topics:
        topic_title = topic.get("topic", "")
        eng = engagement.get(topic_title, 0.0)
        eng_hint = f"，往期互动≈{eng:.0f}" if eng > 0 else ""
        view = topic.get("view_count")
        view_hint = f"，浏览{view}" if view else ""
        items.append(
            {
                "source_kind": "topic",
                "title": topic_title,
                "summary": f"参与{topic.get('participation_count', '?')}{view_hint}{eng_hint}",
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
