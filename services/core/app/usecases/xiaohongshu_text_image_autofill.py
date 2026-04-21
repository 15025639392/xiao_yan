from __future__ import annotations

import json
import time

from app.api.platform_route_models import XiaohongshuTextImageAutofillResponse
from app.api.tool_capability_bridge import (
    BrowserCapabilityError,
    BrowserOrganUnavailable,
    call_browser_capability,
)
from app.usecases.xiaohongshu_publish_autofill import _PUBLISH_URL
from app.usecases.xiaohongshu_text_image_script import build_text_image_script


def autofill_xiaohongshu_text_image_cards(
    *,
    cards: list[str],
    trigger_generate: bool = True,
) -> XiaohongshuTextImageAutofillResponse:
    normalized_cards = [card.strip() for card in cards if card.strip()]
    if not normalized_cards:
        raise ValueError("text image cards cannot be empty")

    try:
        open_result = call_browser_capability(
            "browser.open",
            {"url": _PUBLISH_URL, "headless": False},
            timeout_seconds=15.0,
        )
    except BrowserOrganUnavailable:
        return XiaohongshuTextImageAutofillResponse(
            status="browser_unavailable",
            publish_url=_PUBLISH_URL,
            cards=normalized_cards,
            filled_cards=0,
            clicked_generate=False,
            message="浏览器器官不可用，请先确认桌面端浏览器器官在线。",
        )

    session_id = open_result.get("session_id")
    if not session_id:
        return XiaohongshuTextImageAutofillResponse(
            status="open_failed",
            publish_url=_PUBLISH_URL,
            cards=normalized_cards,
            filled_cards=0,
            clicked_generate=False,
            message="打开小红书发布页失败。",
        )

    try:
        time.sleep(0.8)
        raw_result = _run_text_image_script_with_retry(
            session_id=session_id,
            cards=normalized_cards,
            trigger_generate=trigger_generate,
        )
        try:
            payload = json.loads(raw_result)
        except json.JSONDecodeError as exc:
            raise ValueError("unexpected xiaohongshu text image autofill result") from exc
    finally:
        _ensure_close(session_id)

    status = str(payload.get("status") or "missing_editor")
    filled_cards = int(payload.get("filled_cards") or 0)
    clicked_generate = bool(payload.get("clicked_generate"))
    if status == "partial_cards" and filled_cards < len(normalized_cards):
        status = "needs_manual_expand"
    return XiaohongshuTextImageAutofillResponse(
        status=status,
        publish_url=_PUBLISH_URL,
        cards=normalized_cards,
        filled_cards=filled_cards,
        clicked_generate=clicked_generate,
        message=_build_result_message(
            status=status,
            filled_cards=filled_cards,
            expected_cards=len(normalized_cards),
            clicked_generate=clicked_generate,
        ),
    )


def _run_text_image_script_with_retry(*, session_id: str, cards: list[str], trigger_generate: bool) -> str:
    script = build_text_image_script(cards=cards, trigger_generate=trigger_generate)
    last_result = ""
    for attempt in range(6):
        last_result = _evaluate_browser_script(session_id, script)
        compact = last_result.replace(" ", "")
        needs_retry = (
            '"status":"missing_editor"' in compact
            or '"status":"opened_text_to_image"' in compact
            or '"status":"partial_cards"' in compact
        )
        if not needs_retry:
            return last_result
        if attempt < 5:
            time.sleep(0.8)
    return last_result


def _evaluate_browser_script(session_id: str, script: str) -> str:
    try:
        result = call_browser_capability(
            "browser.evaluate",
            {"session_id": session_id, "script": script},
            timeout_seconds=12.0,
        )
    except BrowserCapabilityError as exc:
        raise ValueError(f"browser evaluate failed: {exc}") from exc
    raw_result = result.get("result", "")
    if isinstance(raw_result, str):
        return raw_result
    return json.dumps(raw_result, ensure_ascii=False)


def _ensure_close(session_id: str) -> None:
    try:
        call_browser_capability(
            "browser.close",
            {"session_id": session_id},
            timeout_seconds=5.0,
        )
    except Exception:
        pass


def _build_result_message(*, status: str, filled_cards: int, expected_cards: int, clicked_generate: bool) -> str:
    if status == "submitted_generation":
        return f"已把 {filled_cards}/{expected_cards} 张图卡文案填进文字配图，并触发了生成图片。"
    if status == "filled_cards":
        return f"已把 {filled_cards}/{expected_cards} 张图卡文案填进文字配图，你可以继续检查后再点生成图片。"
    if status == "needs_manual_expand":
        remaining = max(expected_cards - filled_cards, 0)
        return (
            f"已先填入 {filled_cards}/{expected_cards} 张图卡文案。"
            f"还剩 {remaining} 张。请先在小红书页面点一次“再写一张”，再回到小晏点“继续填正文页”。"
        )
    if status == "partial_cards":
        return f"已先填入 {filled_cards}/{expected_cards} 张图卡文案，剩余图卡仍在继续展开。"
    if status == "opened_text_to_image":
        return "已打开文字配图入口，但编辑区还没完全出现，请稍等后再试一次。"
    return "已打开发布页，但暂时没识别到文字配图编辑区。"

