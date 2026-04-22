"""Fetch engagement metrics for recently-published XHS posts via browser snapshot."""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.api.tool_capability_bridge import BrowserCapabilityError, call_browser_capability


_METRICS_URL_PREFIXES = (
    "https://www.xiaohongshu.com/",
    "https://creator.xiaohongshu.com/",
)

_COUNT_PATTERNS = {
    "like_count": [r"点赞(?:数)?[:：]?\s*([0-9]+(?:\.[0-9]+)?[万wW]?)", r"获赞[:：]?\s*([0-9]+(?:\.[0-9]+)?[万wW]?)"],
    "collect_count": [r"收藏(?:数)?[:：]?\s*([0-9]+(?:\.[0-9]+)?[万wW]?)"],
    "comment_count": [r"评论(?:数)?[:：]?\s*([0-9]+(?:\.[0-9]+)?[万wW]?)"],
    "share_count": [r"分享(?:数)?[:：]?\s*([0-9]+(?:\.[0-9]+)?[万wW]?)"],
    "view_count": [r"(?:浏览|阅读|曝光)(?:数)?[:：]?\s*([0-9]+(?:\.[0-9]+)?[万wW]?)"],
}


@dataclass(frozen=True)
class PostEngagementMetrics:
    like_count: str | None
    collect_count: str | None
    comment_count: str | None
    share_count: str | None
    view_count: str | None
    fetched_at: str


def capture_xiaohongshu_post_metrics(
    *,
    session_id: str,
) -> PostEngagementMetrics:
    """Snapshot the current browser page and extract engagement metrics."""
    try:
        snapshot = call_browser_capability(
            "browser.snapshot",
            {"session_id": session_id, "include_text": True},
            timeout_seconds=15.0,
        )
    except BrowserCapabilityError:
        raise ValueError("browser organ snapshot failed for metrics capture")

    raw_text = str(snapshot.get("text_content") or "")
    return _extract_metrics_from_text(raw_text)


def extract_metrics_from_text(raw_text: str) -> PostEngagementMetrics:
    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    counts = {field: _find_metric_value(lines, patterns) for field, patterns in _COUNT_PATTERNS.items()}
    return PostEngagementMetrics(
        like_count=counts.get("like_count"),
        collect_count=counts.get("collect_count"),
        comment_count=counts.get("comment_count"),
        share_count=counts.get("share_count"),
        view_count=counts.get("view_count"),
        fetched_at="",
    )


def _find_metric_value(lines: list[str], patterns: list[str]) -> str | None:
    for line in lines:
        compact = line.replace(" ", "")
        for pattern in patterns:
            match = re.search(pattern, compact, re.IGNORECASE)
            if match:
                return match.group(1)
    return None


def fetch_metrics_for_history(
    history: list[dict],
    session_id: str,
    post_url: str,
) -> list[dict]:
    """Fetch engagement metrics for the most recent unpublished-history entry.

    Opens the post URL in the given session, snapshots the page, and patches
    the matching history entry's ``metrics`` field in place. Returns the
    updated history list.
    """
    # Find entries without metrics or with empty metrics
    target_idx = None
    for i, entry in enumerate(history):
        metrics = entry.get("metrics") or {}
        if not metrics or not any(metrics.get(k) for k in ("like_count", "collect_count", "comment_count")):
            target_idx = i
            break

    if target_idx is None:
        return history

    # Open the post page
    call_browser_capability(
        "browser.open",
        {"url": post_url, "session_id": session_id, "headless": False, "activate": False},
        timeout_seconds=20.0,
    )

    metrics_data = capture_xiaohongshu_post_metrics(session_id=session_id)
    updated_metrics = {
        "like_count": metrics_data.like_count,
        "collect_count": metrics_data.collect_count,
        "comment_count": metrics_data.comment_count,
        "share_count": metrics_data.share_count,
        "view_count": metrics_data.view_count,
    }

    history = list(history)
    history[target_idx] = {**history[target_idx], "metrics": updated_metrics}
    return history
