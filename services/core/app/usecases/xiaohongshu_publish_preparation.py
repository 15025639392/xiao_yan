from __future__ import annotations

from typing import Any, Callable

from app.api.tool_capability_bridge import BrowserCapabilityError, BrowserOrganUnavailable
from app.usecases.xiaohongshu_cover_image import XiaohongshuCoverImageGenerationError, XiaohongshuCoverImageUnavailableError
from app.usecases.xiaohongshu_content_strategy import normalize_xiaohongshu_body, normalize_xiaohongshu_title


def prepare_xiaohongshu_publish_draft(draft: dict[str, Any]) -> dict[str, Any]:
    normalized_draft = dict(draft)
    fallback_title = "小晏先讲这个瞬间"
    title = normalize_xiaohongshu_title(str(draft.get("title", "")), fallback=fallback_title)
    body = normalize_xiaohongshu_body(str(draft.get("body", "")))
    if not body:
        source_title = str(draft.get("opportunity_title", "")).strip() or title
        body = _build_light_science_publish_body(title=title, source_title=source_title)

    normalized_draft["title"] = title
    normalized_draft["body"] = body
    return normalized_draft


def _build_light_science_publish_body(*, title: str, source_title: str) -> str:
    source_label = source_title if source_title.startswith("#") else f"“{source_title}”"
    return normalize_xiaohongshu_body(
        (
            f"看到 {source_label} 的时候，我先想到的不是跟风，而是很多人会在类似瞬间里突然被自己的情绪轻轻撞一下。\n\n"
            f"{title} 这种感受，很多时候不是你太敏感，而是那件事刚好碰到了你心里还没来得及说清的位置。\n\n"
            "如果你也有过这种时候，小晏可以继续陪你慢慢把它讲明白。"
        )
    )


def build_xiaohongshu_browser_publish_image_paths(
    draft: dict[str, Any],
    *,
    generate_cover_image: Callable[..., Any],
) -> list[str]:
    raw_image_paths = draft.get("image_paths")
    if isinstance(raw_image_paths, list):
        normalized = [str(item).strip() for item in raw_image_paths if str(item).strip()]
        if normalized:
            return normalized

    title = str(draft.get("title", "")).strip()
    body = str(draft.get("body", "")).strip()
    if not title or not body:
        return []
    try:
        generated_cover = generate_cover_image(title=title, body=body)
    except (XiaohongshuCoverImageUnavailableError, XiaohongshuCoverImageGenerationError):
        return []
    if generated_cover is None:
        return []
    return [generated_cover.path]


def find_xiaohongshu_publish_button(
    *,
    publish_url: str,
    call_browser_capability: Callable[..., dict[str, Any]],
    close_session: Callable[[str], None],
) -> str | None:
    try:
        open_result = call_browser_capability(
            "browser.open",
            {"url": publish_url, "headless": False},
            timeout_seconds=15.0,
        )
    except (BrowserOrganUnavailable, BrowserCapabilityError):
        return None

    session_id = str(open_result.get("session_id") or "").strip()
    if not session_id:
        return None

    try:
        result = call_browser_capability(
            "browser.find_publish_button",
            {"session_id": session_id},
            timeout_seconds=10.0,
        )
        if result.get("found"):
            return result.get("selector")
        return None
    except (BrowserCapabilityError, BrowserOrganUnavailable):
        return None
    finally:
        close_session(session_id)
