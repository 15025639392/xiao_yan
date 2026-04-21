from __future__ import annotations

import re
from dataclasses import dataclass

from app.api.platform_route_models import (
    XiaohongshuActivityOpportunitySnapshot,
    XiaohongshuCreatorHomeCaptureResponse,
    XiaohongshuTopicOpportunitySnapshot,
)
from app.api.tool_capability_bridge import (
    BrowserCapabilityError,
    BrowserOrganUnavailable,
    call_browser_capability,
)


_EXPECTED_URL_PREFIX = "https://creator.xiaohongshu.com/new/home"
_CREATOR_HOME_SESSION_ID = "xhs-login"
_ACCOUNT_NAME_GENERIC_LINES = {
    "遇到问题",
    "创作服务平台",
    "发布笔记",
    "首页",
    "笔记管理",
    "数据看板",
    "活动中心",
    "笔记灵感",
    "创作学院",
    "创作百科",
    "收起侧边栏",
    "关注数",
    "粉丝数",
    "获赞与收藏",
    "还没有简介",
    "新的创作",
    "查看详情",
    "近7日",
    "近30日",
    "创作话题",
    "创作资讯",
    "热门活动",
    "成长榜样",
    "查看更多",
}
_ACCOUNT_NAME_GENERIC_SUBSTRINGS = (
    "服务平台",
    "创作",
    "发布",
    "笔记",
    "数据",
    "活动",
    "账号",
    "简介",
    "统计周期",
    "环比",
    "支持",
)


def capture_xiaohongshu_creator_home_via_browser_organ() -> XiaohongshuCreatorHomeCaptureResponse:
    try:
        open_result = call_browser_capability(
            "browser.open",
            {
                "url": _EXPECTED_URL_PREFIX,
                "session_id": _CREATOR_HOME_SESSION_ID,
                "headless": False,
                "activate": False,
            },
            timeout_seconds=20.0,
        )
    except BrowserOrganUnavailable as exc:
        raise ValueError("browser organ unavailable for xiaohongshu creator home capture") from exc

    session_id = str(open_result.get("session_id") or "").strip()
    if not session_id:
        raise ValueError("browser organ did not return a session for xiaohongshu creator home capture")

    try:
        snapshot = call_browser_capability(
            "browser.snapshot",
            {"session_id": session_id, "include_text": True},
            timeout_seconds=15.0,
        )
    except BrowserCapabilityError as exc:
        raise ValueError("browser organ snapshot failed for xiaohongshu creator home capture") from exc
    source_url = str(snapshot.get("url") or open_result.get("resolved_url") or _EXPECTED_URL_PREFIX)
    if not source_url.startswith(_EXPECTED_URL_PREFIX):
        raise ValueError("browser organ is not on xiaohongshu creator home")

    raw_text = str(snapshot.get("text_content") or "")
    extracted = extract_creator_home_from_raw_text(raw_text)
    return XiaohongshuCreatorHomeCaptureResponse(
        source_url=source_url,
        account_name=extracted.account_name,
        raw_text=raw_text,
        topics=extracted.topics,
        activities=extracted.activities,
    )


@dataclass(frozen=True)
class CreatorHomeExtraction:
    account_name: str | None
    topics: list[XiaohongshuTopicOpportunitySnapshot]
    activities: list[XiaohongshuActivityOpportunitySnapshot]


def extract_creator_home_from_raw_text(raw_text: str) -> CreatorHomeExtraction:
    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    account_name = _extract_account_name(lines)
    topics: list[XiaohongshuTopicOpportunitySnapshot] = []
    activities: list[XiaohongshuActivityOpportunitySnapshot] = []
    pending_activity_hint: str | None = None

    index = 0
    while index < len(lines):
        current = lines[index]
        next_line = lines[index + 1] if index + 1 < len(lines) else ""

        if current.startswith("#"):
            participation_count = None
            view_count = None
            if "参与" in next_line or "浏览" in next_line:
                parts = [part.strip() for part in next_line.split("，")]
                participation_count = parts[0] if parts else None
                view_count = parts[1] if len(parts) > 1 else None
                index += 1
            topics.append(
                XiaohongshuTopicOpportunitySnapshot(
                    topic=current,
                    participation_count=participation_count,
                    view_count=view_count,
                )
            )
        elif "官方活动" in current or "奖励" in current:
            pending_activity_hint = current
        else:
            activity_source = current
            if pending_activity_hint and " 至 " not in current and " 至 " in next_line:
                activity_source = f"{current} {next_line}"
                index += 1
            activity = _parse_activity_line(activity_source, pending_activity_hint)
            if activity is not None:
                activities.append(activity)
        index += 1

    return CreatorHomeExtraction(
        account_name=account_name,
        topics=topics,
        activities=activities,
    )


def _extract_account_name(lines: list[str]) -> str | None:
    account_name = next((line for line in lines if line.startswith("小红薯")), None)
    if account_name:
        return account_name

    account_name = next((line for line in lines if "小红薯" in line), None)
    if account_name:
        return account_name

    top_lines = lines[:24]
    candidate_counts: dict[str, int] = {}
    for line in top_lines:
        if _looks_like_account_name(line):
            candidate_counts[line] = candidate_counts.get(line, 0) + 1

    for line in top_lines:
        if candidate_counts.get(line, 0) >= 2:
            return line

    for marker in ("关注数", "粉丝数", "获赞与收藏"):
        marker_index = next((index for index, line in enumerate(top_lines) if line == marker), -1)
        if marker_index < 0:
            continue
        for candidate in reversed(top_lines[max(0, marker_index - 3):marker_index]):
            if _looks_like_account_name(candidate):
                return candidate

    account_id_index = next((index for index, line in enumerate(lines[:30]) if line.startswith("小红书账号:")), -1)
    if account_id_index >= 0:
        for candidate in reversed(lines[max(0, account_id_index - 8):account_id_index]):
            if _looks_like_account_name(candidate):
                return candidate

    return None


def _looks_like_account_name(line: str) -> bool:
    value = line.strip()
    if not value or len(value) > 20:
        return False
    if value in _ACCOUNT_NAME_GENERIC_LINES:
        return False
    if any(token in value for token in _ACCOUNT_NAME_GENERIC_SUBSTRINGS):
        return False
    if value.startswith("#"):
        return False
    if re.fullmatch(r"[0-9.%/+\-]+", value):
        return False
    if value.endswith("数"):
        return False
    return True


def _parse_activity_line(
    value: str,
    incentive_hint: str | None,
) -> XiaohongshuActivityOpportunitySnapshot | None:
    if incentive_hint is None:
        return None
    marker = " 至 "
    if marker not in value:
        return None
    parts = value.rsplit(" ", 3)
    if len(parts) < 4:
        return None
    title = parts[0].strip()
    date_range = " ".join(parts[1:]).strip()
    if not title or not date_range:
        return None
    if title in {"统计周期"}:
        return None
    return XiaohongshuActivityOpportunitySnapshot(
        title=title,
        date_range=date_range,
        incentive_hint=incentive_hint,
    )


def _close_browser_session(session_id: str) -> None:
    if session_id == _CREATOR_HOME_SESSION_ID:
        return
    try:
        call_browser_capability(
            "browser.close",
            {"session_id": session_id},
            timeout_seconds=5.0,
        )
    except Exception:
        pass
