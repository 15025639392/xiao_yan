from __future__ import annotations

import json


def build_text_image_script(*, cards: list[str], trigger_generate: bool) -> str:
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
