from __future__ import annotations

from dataclasses import dataclass
import re

from app.api.platform_route_models import XiaohongshuLeadCaptureResponse
from app.usecases.xiaohongshu_chrome_capture import capture_active_chrome_tab


_SUPPORTED_URL_PREFIXES = (
    "https://creator.xiaohongshu.com/",
    "https://www.xiaohongshu.com/",
)

_COUNT_PATTERNS = {
    "like_count": [r"点赞(?:数)?[:：]?\s*([0-9]+(?:\.[0-9]+)?[万wW]?)", r"获赞[:：]?\s*([0-9]+(?:\.[0-9]+)?[万wW]?)"],
    "collect_count": [r"收藏(?:数)?[:：]?\s*([0-9]+(?:\.[0-9]+)?[万wW]?)"],
    "comment_count": [r"评论(?:数)?[:：]?\s*([0-9]+(?:\.[0-9]+)?[万wW]?)"],
    "share_count": [r"分享(?:数)?[:：]?\s*([0-9]+(?:\.[0-9]+)?[万wW]?)"],
}
_DIRECT_MESSAGE_KEYWORDS = ("私信", "私聊", "联系你", "联系我")
_WECHAT_KEYWORDS = ("微信", "vx", "v信", "加v", "加微")
_PURCHASE_KEYWORDS = ("多少钱", "价格", "报价", "收费", "购买", "下单", "报名", "合作", "预算", "方案")
_LEAD_KEYWORDS = (
    "怎么",
    "如何",
    "适合",
    "可以吗",
    "模板",
    "教程",
    "私信",
    "微信",
    "价格",
    "报价",
    "合作",
    "方案",
)
_NOISE_PREFIXES = ("创作服务平台", "创作话题", "热门活动", "数据中心", "服务", "发布")


@dataclass(frozen=True)
class LeadCaptureExtraction:
    note_title: str
    like_count: str | None
    collect_count: str | None
    comment_count: str | None
    share_count: str | None
    direct_message_signal_count: int
    wechat_signal_count: int
    purchase_signal_count: int
    lead_keywords: list[str]
    matched_comment_lines: list[str]
    tracking_template: str


def capture_xiaohongshu_lead_signals_from_chrome(*, title_hint: str | None = None) -> XiaohongshuLeadCaptureResponse:
    captured = capture_active_chrome_tab()
    if not any(captured.url.startswith(prefix) for prefix in _SUPPORTED_URL_PREFIXES):
        raise ValueError("active Chrome tab is not a supported xiaohongshu page")

    extracted = extract_lead_capture_from_raw_text(captured.body_text, title_hint=title_hint)
    return XiaohongshuLeadCaptureResponse(
        source_url=captured.url,
        note_title=extracted.note_title,
        raw_text=captured.body_text,
        like_count=extracted.like_count,
        collect_count=extracted.collect_count,
        comment_count=extracted.comment_count,
        share_count=extracted.share_count,
        direct_message_signal_count=extracted.direct_message_signal_count,
        wechat_signal_count=extracted.wechat_signal_count,
        purchase_signal_count=extracted.purchase_signal_count,
        lead_keywords=extracted.lead_keywords,
        matched_comment_lines=extracted.matched_comment_lines,
        tracking_template=extracted.tracking_template,
        message=_build_capture_message(extracted),
    )


def extract_lead_capture_from_raw_text(raw_text: str, *, title_hint: str | None = None) -> LeadCaptureExtraction:
    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    note_title = _resolve_note_title(lines, title_hint=title_hint)
    counts = {field: _find_metric_value(lines, patterns) for field, patterns in _COUNT_PATTERNS.items()}

    matched_comment_lines: list[str] = []
    keyword_hits: list[str] = []
    direct_message_signal_count = 0
    wechat_signal_count = 0
    purchase_signal_count = 0

    for line in lines:
        lower_line = line.lower()
        is_lead_line = any(keyword in line for keyword in _LEAD_KEYWORDS)
        if is_lead_line and line not in matched_comment_lines:
            matched_comment_lines.append(line)
            keyword_hits.extend(keyword for keyword in _LEAD_KEYWORDS if keyword in line and keyword not in keyword_hits)
        if any(keyword in line for keyword in _DIRECT_MESSAGE_KEYWORDS):
            direct_message_signal_count += 1
        if any(keyword in lower_line for keyword in _WECHAT_KEYWORDS):
            wechat_signal_count += 1
        if any(keyword in line for keyword in _PURCHASE_KEYWORDS):
            purchase_signal_count += 1

    matched_comment_lines = matched_comment_lines[:5]
    lead_keywords = keyword_hits[:8]
    tracking_template = _build_tracking_template(
        note_title=note_title,
        like_count=counts["like_count"],
        collect_count=counts["collect_count"],
        comment_count=counts["comment_count"],
        share_count=counts["share_count"],
        direct_message_signal_count=direct_message_signal_count,
        wechat_signal_count=wechat_signal_count,
        purchase_signal_count=purchase_signal_count,
        lead_keywords=lead_keywords,
        matched_comment_lines=matched_comment_lines,
    )

    return LeadCaptureExtraction(
        note_title=note_title,
        like_count=counts["like_count"],
        collect_count=counts["collect_count"],
        comment_count=counts["comment_count"],
        share_count=counts["share_count"],
        direct_message_signal_count=direct_message_signal_count,
        wechat_signal_count=wechat_signal_count,
        purchase_signal_count=purchase_signal_count,
        lead_keywords=lead_keywords,
        matched_comment_lines=matched_comment_lines,
        tracking_template=tracking_template,
    )


def _resolve_note_title(lines: list[str], *, title_hint: str | None) -> str:
    normalized_hint = (title_hint or "").strip()
    if normalized_hint:
        return normalized_hint
    for line in lines:
        if any(line.startswith(prefix) for prefix in _NOISE_PREFIXES):
            continue
        if line.startswith("#"):
            continue
        if len(line) < 6:
            continue
        return line
    return "当前小红书内容"


def _find_metric_value(lines: list[str], patterns: list[str]) -> str | None:
    for line in lines:
        compact_line = line.replace(" ", "")
        for pattern in patterns:
            match = re.search(pattern, compact_line, re.IGNORECASE)
            if match:
                return match.group(1)
    return None


def _build_tracking_template(
    *,
    note_title: str,
    like_count: str | None,
    collect_count: str | None,
    comment_count: str | None,
    share_count: str | None,
    direct_message_signal_count: int,
    wechat_signal_count: int,
    purchase_signal_count: int,
    lead_keywords: list[str],
    matched_comment_lines: list[str],
) -> str:
    return "\n".join(
        [
            f"内容标题：{note_title}",
            "发布时间：",
            f"点赞数：{like_count or ''}",
            f"收藏数：{collect_count or ''}",
            f"评论数量：{comment_count or ''}",
            f"分享数：{share_count or ''}",
            f"进入私信人数：{direct_message_signal_count}",
            f"导到微信人数：{wechat_signal_count}",
            f"成交前置信号：{purchase_signal_count} 条",
            f"有效评论关键词：{', '.join(lead_keywords) if lead_keywords else ''}",
            "最终结果：",
            "下一轮要放大的点：",
            "",
            "当前页命中的线索评论：",
            *(f"{index + 1}. {line}" for index, line in enumerate(matched_comment_lines or ["暂无自动命中的高意向评论，请补人工观察。"])),
            "",
            "复盘问题：",
            "1. 哪类评论最容易转到私信？",
            "2. 哪一句回复最容易把人往成交前推进？",
            "3. 这条内容更适合引流，还是更适合成交？",
        ]
    )


def _build_capture_message(extracted: LeadCaptureExtraction) -> str:
    metric_parts = [
        f"评论 {extracted.comment_count}" if extracted.comment_count else None,
        f"点赞 {extracted.like_count}" if extracted.like_count else None,
        f"收藏 {extracted.collect_count}" if extracted.collect_count else None,
    ]
    base = "已从当前小红书页面提取经营线索"
    metrics = "，".join(part for part in metric_parts if part)
    if metrics:
        base = f"{base}：{metrics}"
    if extracted.matched_comment_lines:
        return f"{base}，并命中 {len(extracted.matched_comment_lines)} 条值得跟进的评论线索。"
    return f"{base}，但暂时没命中明显高意向评论。"
