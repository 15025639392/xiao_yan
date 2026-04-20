from __future__ import annotations

from app.platform_adapters.models import CanonicalEvent, LeadAssessment


HIGH_INTENT_KEYWORDS = ("多少钱", "价格", "怎么购买", "怎么买", "咨询", "合作", "课程", "服务", "报名")
MEDIUM_INTENT_KEYWORDS = ("适合", "可以吗", "怎么做", "如何", "教程", "链接", "详细", "步骤")


def assess_xiaohongshu_lead(event: CanonicalEvent) -> LeadAssessment:
    text = (event.text or "").strip()
    source_scene = str(event.metadata.get("source_scene") or "").strip()
    combined_context = " ".join(
        part for part in [text, str(event.metadata.get("topic") or ""), str(event.metadata.get("note_title") or "")]
        if part
    )

    if source_scene == "creator_home":
        return LeadAssessment(
            platform="xiaohongshu",
            is_lead=False,
            intent_level="low",
            lead_stage="observe",
            suggested_action="prepare_note",
            follow_up_hint="这是创作首页机会，更适合作为选题和草稿继续验证，再等真实互动线索出现。",
            reasons=["来源于创作首页机会池，优先进入内容生产闭环"],
        )

    if not text:
        return LeadAssessment(
            platform="xiaohongshu",
            is_lead=False,
            intent_level="low",
            lead_stage="ignore",
            suggested_action="ignore",
            reasons=["内容为空，暂不进入经营流程"],
        )

    reasons: list[str] = []
    if _contains_keyword(combined_context, HIGH_INTENT_KEYWORDS):
        reasons.append("出现高意向咨询词")
        return LeadAssessment(
            platform="xiaohongshu",
            is_lead=True,
            intent_level="high",
            lead_stage="follow_up",
            suggested_action="follow_up_manually",
            follow_up_hint="优先回复评论，并准备转入更具体的一对一跟进。",
            reasons=reasons,
        )

    if _contains_keyword(combined_context, MEDIUM_INTENT_KEYWORDS) or event.event_type == "comment":
        if _contains_keyword(combined_context, MEDIUM_INTENT_KEYWORDS):
            reasons.append("出现中意向提问词")
        if event.event_type == "comment":
            reasons.append("评论互动更适合作为线索观察入口")
        return LeadAssessment(
            platform="xiaohongshu",
            is_lead=True,
            intent_level="medium",
            lead_stage="engage",
            suggested_action="reply_comment",
            follow_up_hint="先给低压力、高信息密度的评论回复，再观察是否继续追问。",
            reasons=reasons,
        )

    reasons.append("更像内容曝光素材，暂不作为强线索推进")
    return LeadAssessment(
        platform="xiaohongshu",
        is_lead=False,
        intent_level="low",
        lead_stage="observe",
        suggested_action="prepare_note",
        follow_up_hint="更适合作为内容选题或笔记草稿继续经营。",
        reasons=reasons,
    )


def _contains_keyword(text: str, keywords: tuple[str, ...]) -> bool:
    normalized = text.lower()
    return any(keyword in normalized for keyword in keywords)
