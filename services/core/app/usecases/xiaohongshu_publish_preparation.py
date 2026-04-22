from __future__ import annotations

import re
from typing import Any, Callable

from app.api.tool_capability_bridge import BrowserCapabilityError, BrowserOrganUnavailable
from app.usecases.xiaohongshu_cover_image import (
    XiaohongshuCoverImageGenerationError,
    XiaohongshuCoverImageUnavailableError,
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


def prepare_xiaohongshu_text_image_cards_for_draft(
    draft: dict[str, Any],
    *,
    autofill_cards: Callable[..., Any],
) -> dict[str, str] | None:
    cards = _build_text_image_cards_from_draft(draft)
    if not cards:
        return None

    try:
        result = autofill_cards(cards=cards, trigger_generate=True)
    except (BrowserOrganUnavailable, BrowserCapabilityError):
        return {
            "status": "browser_unavailable",
            "message": "浏览器器官不可用，请稍后再试",
            "focus": "浏览器器官暂时不可用",
        }
    except ValueError:
        return None

    status = result.status
    if status == "browser_unavailable":
        return None

    focus = "已进入补图阶段，等待图片生成后再继续发布"
    if status == "submitted_generation":
        focus = f"已填入 {result.filled_cards}/{len(cards)} 张图卡并触发生成图片"
    elif status == "needs_manual_expand":
        focus = "已填入部分图卡，请在发布页点一次“再写一张”后继续"
    elif status == "filled_cards":
        focus = f"已填入 {result.filled_cards}/{len(cards)} 张图卡，等待继续补图"
    elif status == "opened_text_to_image":
        focus = "已打开文字配图入口，等待编辑区出现"

    return {
        "status": status,
        "message": result.message,
        "focus": focus,
    }


def _build_text_image_cards_from_draft(draft: dict[str, Any]) -> list[str]:
    raw_cards = draft.get("image_cards")
    if isinstance(raw_cards, list):
        normalized = [str(item).strip() for item in raw_cards if str(item).strip()]
        if normalized:
            return normalized[:3]

    title = str(draft.get("title", "")).strip()
    body = str(draft.get("body", "")).strip()
    paragraphs = [
        segment.strip()
        for segment in re.split(r"\n\s*\n|\n", body)
        if segment.strip()
    ]

    cards: list[str] = []
    if title:
        cards.append(title)
    if paragraphs:
        cards.append(paragraphs[0])
        remainder = "\n".join(paragraphs[1:]).strip()
        if remainder:
            cards.append(remainder)
    elif body:
        cards.append(body)

    deduped: list[str] = []
    for item in cards:
        if item and item not in deduped:
            deduped.append(item)
    return deduped[:3]
