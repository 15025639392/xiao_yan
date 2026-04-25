from __future__ import annotations

import re
from dataclasses import dataclass

from app.usecases.xiaohongshu_cover_templates import (
    XiaohongshuCoverTemplate,
    get_xiaohongshu_cover_template,
)


_TEMPLATE_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("bold_hook", (
        "别再", "千万", "为什么", "误区", "真相", "劝你", "不要再", "一定要",
        "别做", "不会做", "不知道", "还以为", "你还在", "错了", "注意",
        "竟然", "惊人", "绝了", "太", "必看", "千万别",
    )),
    ("warm_story", (
        "我", "最近", "今天", "经历", "感受", "日常", "故事", "复盘",
        "慢慢", "坚持", "终于", "第一次", "曾经", "学会了", "原来",
        "治愈", "温暖", "陪伴", "一个人", "生活", "记录",
    )),
    ("playful_pop", (
        "开箱", "测评", "种草", "好物", "推荐", "打卡", "探店", "美食",
        "穿搭", "护肤", "化妆", "减肥", "运动", "旅行", "拍照",
        "可爱", "有趣", "搞笑", "酷", "潮", "宝藏", "安利",
    )),
    ("dark_moody", (
        "深夜", "深度", "反思", "思考", "哲学", "人生", "意义", "孤独",
        "挣扎", "痛苦", "迷茫", "焦虑", "内耗", "边界", "底线",
        "灵魂", "真相", "本质", "内核", "清醒", "克制",
    )),
    ("minimal_clean", (
        "极简", "整理", "方法", "总结", "效率", "习惯", "规划", "清单",
        "原则", "逻辑", "分析", "拆解", "框架", "体系", "认知",
        "思维", "知识", "学习", "成长", "规律", "底层",
    )),
    ("expert_clean", (
        "步骤", "方法", "教程", "清单", "怎么做", "攻略", "模板", "技巧",
        "拆解", "梳理", "框架", "指南", "干货", "总结", "思路",
        "建议", "如何", "掌握", "学习", "提升", "解决",
    )),
)


@dataclass(frozen=True)
class XiaohongshuCoverLayoutDecision:
    template: XiaohongshuCoverTemplate
    subtitle: str
    show_subtitle: bool
    title_size_tier: str  # "short" | "medium" | "long"


def derive_xiaohongshu_cover_subtitle(body: str, *, default_subtitle: str) -> str:
    if not body:
        return default_subtitle

    # Split into candidate sentences: prefer period-delimited sentences over line-breaks
    raw_sentences = re.split(r"[。！？\n]", body)
    candidates: list[str] = []
    for s in raw_sentences:
        cleaned = re.sub(r"\s+", " ", s).strip(" ，、。；…·-")
        if not cleaned:
            continue
        candidates.append(cleaned)

    if not candidates:
        return default_subtitle

    # Score candidates: prefer sentences of 10-28 chars that feel like a teaser
    def _score(s: str) -> int:
        points = 0
        length = len(s)
        if 12 <= length <= 26:
            points += 3
        elif 8 <= length <= 28:
            points += 1
        # Penalize bullet/number/list starts
        if re.match(r"^[\d一二三四五六七八九十]+[\.\、\)）]", s):
            points -= 2
        if re.match(r"^[·•●◦\-—]", s):
            points -= 2
        # Prefer sentences that end with key indicators
        if any(kw in s for kw in ("发现", "感受", "方法", "秘诀", "关键", "问题", "建议", "不再", "终于")):
            points += 1
        return points

    best = max(candidates, key=_score)
    if not best:
        return default_subtitle
    if len(best) <= 28:
        return best
    return best[:27].rstrip(" ，、。；") + "…"


def choose_xiaohongshu_cover_template_name(*, title: str, body: str) -> str:
    haystack = f"{title}\n{body}".lower()
    scored: list[tuple[str, int]] = []
    for template_name, keywords in _TEMPLATE_KEYWORDS:
        hits = sum(1 for kw in keywords if kw.lower() in haystack)
        if hits > 0:
            scored.append((template_name, hits))
    # Return the template with most keyword hits, fallback to first match in order
    if scored:
        scored.sort(key=lambda x: -x[1])
        return scored[0][0]
    return "expert_clean"


def _title_size_tier(title: str) -> str:
    length = len(title.strip())
    if length <= 12:
        return "short"
    elif length <= 24:
        return "medium"
    return "long"


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
        title_size_tier=_title_size_tier(title),
    )
