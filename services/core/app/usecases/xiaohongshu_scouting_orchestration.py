from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.domain.models import XhsWorkDomainState, XhsWorkStatus


@dataclass(frozen=True)
class XiaohongshuScoutingOutcome:
    last_scouting_data: dict[str, Any]
    action_title: str
    action_data: dict[str, Any]


def is_xiaohongshu_creator_home_login_required(text_content: str) -> bool:
    login_indicators = ["登录", "login", "账号登录", "手机号登录", "密码登录", "验证码登录"]
    text_sample = text_content[:500].lower()
    if not any(ind.lower() in text_sample for ind in login_indicators):
        return False
    return "#" not in text_content[:1000] and "话题" not in text_content[:500]


def apply_xiaohongshu_scouting_result(
    domain: XhsWorkDomainState,
    *,
    extracted: Any,
    text_content: str,
    now: datetime,
) -> XiaohongshuScoutingOutcome:
    topics_data = [
        {"topic": item.topic, "participation_count": item.participation_count, "view_count": item.view_count}
        for item in extracted.topics
    ]
    activities_data = [
        {"title": item.title, "date_range": item.date_range, "incentive_hint": item.incentive_hint}
        for item in extracted.activities
    ]

    topic_count = len(topics_data)
    activity_count = len(activities_data)

    if extracted.account_name:
        domain.profile.account_name = extracted.account_name
    elif topic_count > 0 or activity_count > 0:
        if not domain.profile.account_name or domain.profile.account_name in ("", "当前账号"):
            domain.profile.account_name = "已登录账号"

    domain.state.status = XhsWorkStatus.DRAFTING
    domain.state.last_scouting_at = now
    domain.state.current_focus = f"发现 {topic_count} 个话题、{activity_count} 个活动"
    domain.state.current_bottleneck = ""

    return XiaohongshuScoutingOutcome(
        last_scouting_data={
            "topics": topics_data,
            "activities": activities_data,
            "account_name": extracted.account_name,
            "raw_text": text_content,
        },
        action_title=f"侦察完成：{topic_count} 个话题",
        action_data={"topics": topics_data, "activities": activities_data},
    )
