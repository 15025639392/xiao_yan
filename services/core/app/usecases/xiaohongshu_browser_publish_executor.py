from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from app.api.tool_capability_bridge import BrowserCapabilityError, BrowserOrganUnavailable


@dataclass(frozen=True)
class XiaohongshuPublishSelectorResolution:
    selector: str = ""
    blocked_reason: str = ""


@dataclass(frozen=True)
class XiaohongshuBrowserPublishExecution:
    session_id: str = ""
    publish_result: dict[str, Any] | None = None
    blocked_reason: str = ""
    error: str = ""


def _map_browser_publish_error(error: str, *, phase: str) -> tuple[str, str]:
    normalized = error.strip()
    if "reusable cdp endpoint" in normalized or "cdp endpoint" in normalized:
        return (
            "浏览器器官未暴露可复用调试端口",
            f"{phase}失败: 浏览器器官未暴露可复用调试端口",
        )
    return (f"{phase}失败: {normalized}", normalized)


def resolve_xiaohongshu_publish_selector(
    *,
    requires_manual_review: bool,
    auto_publish_selector: str,
    find_publish_button: Callable[[], str | None],
) -> XiaohongshuPublishSelectorResolution:
    if requires_manual_review:
        return XiaohongshuPublishSelectorResolution()

    selector = auto_publish_selector.strip()
    if selector:
        return XiaohongshuPublishSelectorResolution(selector=selector)

    selector = find_publish_button() or ""
    if selector:
        return XiaohongshuPublishSelectorResolution(selector=selector)

    return XiaohongshuPublishSelectorResolution(blocked_reason="找不到发布按钮")


def execute_xiaohongshu_browser_publish(
    *,
    title: str,
    body: str,
    selector: str,
    image_paths: list[str],
    open_publish_page: Callable[[], dict[str, Any]],
    publish_to_page: Callable[[str, str, str, list[str]], dict[str, Any]],
) -> XiaohongshuBrowserPublishExecution:
    try:
        open_result = open_publish_page()
    except BrowserOrganUnavailable:
        return XiaohongshuBrowserPublishExecution(blocked_reason="浏览器器官不可用", error="browser organ unavailable")
    except BrowserCapabilityError as exc:
        blocked_reason, error = _map_browser_publish_error(str(exc), phase="打开发布页")
        return XiaohongshuBrowserPublishExecution(blocked_reason=blocked_reason, error=error)

    session_id = str(open_result.get("session_id") or "").strip()
    if not session_id:
        return XiaohongshuBrowserPublishExecution(blocked_reason="无法打开发布页")

    try:
        publish_result = publish_to_page(session_id, title, body, selector, image_paths)
    except BrowserCapabilityError as exc:
        blocked_reason, error = _map_browser_publish_error(str(exc), phase="发布")
        return XiaohongshuBrowserPublishExecution(
            session_id=session_id,
            blocked_reason=blocked_reason,
            error=error,
        )

    return XiaohongshuBrowserPublishExecution(
        session_id=session_id,
        publish_result=publish_result,
    )
