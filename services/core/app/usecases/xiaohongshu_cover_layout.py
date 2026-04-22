from __future__ import annotations

import re
from dataclasses import dataclass

from app.usecases.xiaohongshu_cover_templates import (
    XiaohongshuCoverTemplate,
    get_xiaohongshu_cover_template,
)


_TEMPLATE_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("bold_hook", ("别再", "千万", "为什么", "误区", "真相", "劝你", "不要再", "一定要")),
    ("warm_story", ("我", "最近", "今天", "经历", "感受", "日常", "故事", "复盘")),
    ("expert_clean", ("步骤", "方法", "教程", "清单", "怎么做", "攻略", "模板", "技巧")),
)


@dataclass(frozen=True)
class XiaohongshuCoverLayoutDecision:
    template: XiaohongshuCoverTemplate
    subtitle: str
    show_subtitle: bool


def derive_xiaohongshu_cover_subtitle(body: str, *, default_subtitle: str) -> str:
    if not body:
        return default_subtitle
    segments = [segment.strip() for segment in re.split(r"\n\s*\n|\n", body) if segment.strip()]
    candidate = segments[0] if segments else body.strip()
    normalized = re.sub(r"\s+", " ", candidate).strip(" ，、。；…")
    if not normalized:
        return default_subtitle
    if len(normalized) <= 28:
        return normalized
    return normalized[:27].rstrip(" ，、。；") + "…"


def choose_xiaohongshu_cover_template_name(*, title: str, body: str) -> str:
    haystack = f"{title}\n{body}".lower()
    for template_name, keywords in _TEMPLATE_KEYWORDS:
        if any(keyword.lower() in haystack for keyword in keywords):
            return template_name
    return "expert_clean"


def resolve_xiaohongshu_cover_layout(
    *,
    title: str,
    body: str,
    default_subtitle: str,
    template_name: str | None = None,
) -> XiaohongshuCoverLayoutDecision:
    resolved_template_name = template_name or choose_xiaohongshu_cover_template_name(title=title, body=body)
    template = get_xiaohongshu_cover_template(resolved_template_name)
    subtitle = derive_xiaohongshu_cover_subtitle(body, default_subtitle=default_subtitle)
    show_subtitle = len(title.strip()) <= template.hide_subtitle_after_chars and bool(subtitle.strip())
    return XiaohongshuCoverLayoutDecision(
        template=template,
        subtitle=subtitle,
        show_subtitle=show_subtitle,
    )
