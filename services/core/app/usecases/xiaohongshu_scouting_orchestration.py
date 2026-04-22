from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.domain.models import XhsWorkDomainState, XhsWorkStatus

_RAW_TEXT_MAX_CHARS = 2000


@dataclass(frozen=True)
class XhsWorldSnapshot:
    """A structured, self-describing snapshot of the XHS creator world.

    This is the canonical in-memory representation of a scouting capture.
    It is persisted inside XhsWorkState as a dict (via to_dict) so it
    survives service restarts without schema changes.

    Attributes:
        captured_at: When this snapshot was taken.
        topics: Parsed topic entries from the creator home page.
        activities: Parsed activity entries from the creator home page.
        account_name: Detected account name on the page.
        raw_text_truncated: Last _RAW_TEXT_MAX_CHARS characters of the page text,
            kept for debugging. Full raw text is discarded to avoid state bloat.
        topic_count: Number of topics found.
        activity_count: Number of activities found.
        version: Monotonically increasing snapshot version (1 = first capture).
    """

    captured_at: datetime
    topics: list[dict[str, Any]] = field(default_factory=list)
    activities: list[dict[str, Any]] = field(default_factory=list)
    account_name: str | None = None
    raw_text_truncated: str = ""
    topic_count: int = 0
    activity_count: int = 0
    version: int = 1

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict for storage in XhsWorkState.last_scouting_data."""
        return {
            "topics": self.topics,
            "activities": self.activities,
            "account_name": self.account_name,
            "raw_text": self.raw_text_truncated,  # stored under "raw_text" key for compat
            "captured_at": self.captured_at.isoformat(),
            "topic_count": self.topic_count,
            "activity_count": self.activity_count,
            "version": self.version,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "XhsWorldSnapshot":
        """Reconstruct from dict (restored from state)."""
        captured = d.get("captured_at")
        return cls(
            captured_at=datetime.fromisoformat(captured) if captured else datetime.min,
            topics=d.get("topics", []),
            activities=d.get("activities", []),
            account_name=d.get("account_name"),
            raw_text_truncated=d.get("raw_text", ""),
            topic_count=d.get("topic_count", 0),
            activity_count=d.get("activity_count", 0),
            version=d.get("version", 0),
        )


def update_xiaohongshu_world_snapshot(
    domain: XhsWorkDomainState,
    *,
    topics: list[dict[str, Any]],
    activities: list[dict[str, Any]],
    account_name: str | None,
    raw_text: str,
    now: datetime,
) -> XhsWorldSnapshot:
    """Build and persist an XhsWorldSnapshot from the given scouting data.

    This is the single write point for world snapshots. It always:
    - Truncates raw_text to the last _RAW_TEXT_MAX_CHARS characters.
    - Increments the snapshot version from the previous one in state.
    """
    raw_truncated = raw_text[-_RAW_TEXT_MAX_CHARS:] if raw_text else ""

    prev_version = 0
    prev = domain.state.last_scouting_data
    if prev:
        try:
            prev_version = int(prev.get("version", 0))
        except (ValueError, TypeError):
            prev_version = 0

    snapshot = XhsWorldSnapshot(
        captured_at=now,
        topics=topics,
        activities=activities,
        account_name=account_name,
        raw_text_truncated=raw_truncated,
        topic_count=len(topics),
        activity_count=len(activities),
        version=prev_version + 1,
    )

    domain.state.last_scouting_data = snapshot.to_dict()
    return snapshot


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

    # Single write point: build and persist the world snapshot
    snapshot = update_xiaohongshu_world_snapshot(
        domain,
        topics=topics_data,
        activities=activities_data,
        account_name=extracted.account_name,
        raw_text=text_content,
        now=now,
    )

    return XiaohongshuScoutingOutcome(
        last_scouting_data=snapshot.to_dict(),
        action_title=f"侦察完成：{topic_count} 个话题",
        action_data={"topics": topics_data, "activities": activities_data},
    )
