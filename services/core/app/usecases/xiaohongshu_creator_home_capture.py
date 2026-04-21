from __future__ import annotations

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


def capture_xiaohongshu_creator_home_via_browser_organ() -> XiaohongshuCreatorHomeCaptureResponse:
    try:
        open_result = call_browser_capability(
            "browser.open",
            {"url": _EXPECTED_URL_PREFIX, "headless": False},
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
    finally:
        _close_browser_session(session_id)

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
    account_name = next((line for line in lines if line.startswith("小红薯")), None)
    if not account_name:
        account_name = next((line for line in lines if "小红薯" in line), None)
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
    try:
        call_browser_capability(
            "browser.close",
            {"session_id": session_id},
            timeout_seconds=5.0,
        )
    except Exception:
        pass
