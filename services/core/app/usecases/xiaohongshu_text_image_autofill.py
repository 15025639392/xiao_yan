from __future__ import annotations

import json
import time

from app.api.platform_route_models import XiaohongshuTextImageAutofillResponse
from app.usecases.xiaohongshu_publish_autofill import (
    _PUBLISH_URL,
    _execute_active_tab_javascript,
    _open_chrome_publish_page,
)


def autofill_xiaohongshu_text_image_cards(
    *,
    cards: list[str],
    trigger_generate: bool = True,
) -> XiaohongshuTextImageAutofillResponse:
    normalized_cards = [card.strip() for card in cards if card.strip()]
    if not normalized_cards:
        raise ValueError("text image cards cannot be empty")

    _ensure_publish_page_ready()
    time.sleep(0.8)
    raw_result = _run_text_image_script_with_retry(cards=normalized_cards, trigger_generate=trigger_generate)
    try:
        payload = json.loads(raw_result)
    except json.JSONDecodeError as exc:
        raise ValueError("unexpected xiaohongshu text image autofill result") from exc

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


def _ensure_publish_page_ready() -> None:
    current_url = ""
    try:
        current_url = _execute_active_tab_javascript("window.location.href")
    except ValueError:
        current_url = ""
    if "creator.xiaohongshu.com/publish/publish" in current_url:
        return
    _open_chrome_publish_page()


def _run_text_image_script_with_retry(*, cards: list[str], trigger_generate: bool) -> str:
    script = _build_text_image_script(cards=cards, trigger_generate=trigger_generate)
    last_result = ""
    for attempt in range(6):
        last_result = _execute_active_tab_javascript(script)
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


def _build_text_image_script(*, cards: list[str], trigger_generate: bool) -> str:
    payload = json.dumps({"cards": cards, "trigger_generate": trigger_generate}, ensure_ascii=False)
    return f"""
(() => {{
  const payload = {payload};
  const visible = (element) => {{
    if (!element) return false;
    const style = window.getComputedStyle(element);
    const rect = element.getBoundingClientRect();
    return style.visibility !== "hidden" && style.display !== "none" && rect.width > 0 && rect.height > 0;
  }};
  const buttonText = (element) => (element?.innerText || element?.textContent || "").replace(/\\s+/g, "");
  const buttons = () => Array.from(document.querySelectorAll("button, [role='button']")).filter(visible);
  const findButton = (keyword) => buttons().find((element) => buttonText(element).includes(keyword)) || null;
  const findTextNode = (keyword) =>
    Array.from(document.querySelectorAll("div, span, p"))
      .filter(visible)
      .find((element) => buttonText(element) === keyword) || null;
  const findAddSlide = () =>
    Array.from(document.querySelectorAll(".swiper-slide.add-slide, .add-slide"))
      .filter(visible)
      .find((element) => buttonText(element).includes("再写一张")) || null;
  const editorCandidates = () =>
    Array.from(document.querySelectorAll("textarea, [contenteditable='true'], [role='textbox']"))
      .filter(visible)
      .filter((element) => !buttonText(element).includes("再写一张"));
  const performClick = (element) => {{
    if (!element) return false;
    const rect = element.getBoundingClientRect();
    const options = {{
      bubbles: true,
      cancelable: true,
      view: window,
      clientX: rect.left + rect.width / 2,
      clientY: rect.top + rect.height / 2,
    }};
    element.dispatchEvent(new MouseEvent("pointerdown", options));
    element.dispatchEvent(new MouseEvent("mousedown", options));
    element.dispatchEvent(new MouseEvent("pointerup", options));
    element.dispatchEvent(new MouseEvent("mouseup", options));
    element.dispatchEvent(new MouseEvent("click", options));
    if (typeof element.click === "function") {{
      element.click();
    }}
    return true;
  }};
  const setEditableValue = (element, value) => {{
    element.focus();
    if ("value" in element) {{
      const prototype =
        element.tagName.toLowerCase() === "textarea"
          ? window.HTMLTextAreaElement?.prototype
          : window.HTMLInputElement?.prototype;
      const descriptor = prototype ? Object.getOwnPropertyDescriptor(prototype, "value") : null;
      if (descriptor?.set) {{
        descriptor.set.call(element, value);
      }} else {{
        element.value = value;
      }}
      element.dispatchEvent(new Event("input", {{ bubbles: true }}));
      element.dispatchEvent(new Event("change", {{ bubbles: true }}));
      return;
    }}
    const selection = window.getSelection();
    if (selection) {{
      const range = document.createRange();
      range.selectNodeContents(element);
      range.collapse(true);
      selection.removeAllRanges();
      selection.addRange(range);
    }}
    try {{
      document.execCommand("selectAll", false);
      document.execCommand("insertText", false, value);
    }} catch (_error) {{
      // Fall through to direct DOM patch.
    }}
    const currentText = (element.innerText || element.textContent || "").trim();
    if (!currentText) {{
      element.innerHTML = value
        .split("\\n")
        .map((line) => "<p>" + (line || "<br>") + "</p>")
        .join("");
      Array.from(element.querySelectorAll(".is-empty, .is-editor-empty")).forEach((node) => {{
        node.classList.remove("is-empty");
        node.classList.remove("is-editor-empty");
      }});
    }}
    element.dispatchEvent(new InputEvent("beforeinput", {{ bubbles: true, data: value, inputType: "insertText" }}));
    element.dispatchEvent(new InputEvent("input", {{ bubbles: true, data: value, inputType: "insertText" }}));
    element.dispatchEvent(new KeyboardEvent("keyup", {{ bubbles: true, key: "Enter" }}));
    element.dispatchEvent(new Event("change", {{ bubbles: true }}));
    element.dispatchEvent(new Event("blur", {{ bubbles: true }}));
  }};

  let editors = editorCandidates();
  const initialFilledCount = editors.filter((element) => (element.innerText || element.textContent || "").trim()).length;
  if (editors.length === 0 && !findButton("文字配图")) {{
    const imageTab = findTextNode("上传图文");
    if (imageTab) {{
      performClick(imageTab);
      return JSON.stringify({{
        status: "opened_text_to_image",
        filled_cards: 0,
        clicked_generate: false
      }});
    }}
  }}
  if (editors.length === 0) {{
    const textImageButton = findButton("文字配图");
    if (textImageButton) {{
      performClick(textImageButton);
      return JSON.stringify({{
        status: "opened_text_to_image",
        filled_cards: 0,
        clicked_generate: false
      }});
    }}
  }}

  const existingFilledEditors = editors.filter((element) => (element.innerText || element.textContent || "").trim()).length;
  editors.slice(0, payload.cards.length).forEach((element, index) => {{
    const currentText = (element.innerText || element.textContent || "").trim();
    if (currentText) {{
      return;
    }}
    const cardIndex = Math.min(index, payload.cards.length - 1);
    setEditableValue(element, payload.cards[cardIndex]);
  }});
  let filledCards = editors
    .slice(0, payload.cards.length)
    .filter((element) => (element.innerText || element.textContent || "").trim())
    .length;

  if (filledCards > initialFilledCount && filledCards === existingFilledEditors + 1 && editors.length <= filledCards && payload.cards.length > filledCards) {{
    return JSON.stringify({{
      status: "partial_cards",
      filled_cards: filledCards,
      clicked_generate: false
    }});
  }}

  if (filledCards < payload.cards.length) {{
    const addSlide = findAddSlide() || findTextNode("再写一张");
    if (addSlide) {{
      performClick(addSlide);
      return JSON.stringify({{
        status: "partial_cards",
        filled_cards: filledCards,
        clicked_generate: false
      }});
    }}
  }}

  const generateButton = findButton("生成图片");
  const canGenerate = filledCards === payload.cards.length && generateButton;
  if (payload.trigger_generate && canGenerate) {{
    performClick(generateButton);
  }}

  return JSON.stringify({{
    status: payload.trigger_generate && canGenerate ? "submitted_generation" : (filledCards > 0 ? "filled_cards" : "missing_editor"),
    filled_cards: filledCards,
    clicked_generate: Boolean(payload.trigger_generate && canGenerate)
  }});
}})();
"""
