from __future__ import annotations

import json


def build_fill_script(*, title: str, body: str) -> str:
    payload = json.dumps({"title": title, "body": body}, ensure_ascii=False)
    return f"""
(() => {{
  const payload = {payload};
  const visible = (element) => {{
    if (!element) return false;
    const style = window.getComputedStyle(element);
    const rect = element.getBoundingClientRect();
    return style.visibility !== "hidden" && style.display !== "none" && rect.width > 0 && rect.height > 0;
  }};
  const metaText = (element) => {{
    const parts = [
      element.getAttribute("placeholder"),
      element.getAttribute("aria-label"),
      element.getAttribute("name"),
      element.getAttribute("id"),
      element.getAttribute("class"),
      element.getAttribute("data-placeholder"),
    ];
    return parts.filter(Boolean).join(" ").toLowerCase();
  }};
  const setInputValue = (element, value) => {{
    const tagName = element.tagName.toLowerCase();
    const prototype =
      tagName === "textarea" ? window.HTMLTextAreaElement?.prototype : window.HTMLInputElement?.prototype;
    const descriptor = prototype ? Object.getOwnPropertyDescriptor(prototype, "value") : null;
    if (descriptor?.set) {{
      descriptor.set.call(element, value);
    }} else {{
      element.value = value;
    }}
    element.dispatchEvent(new Event("input", {{ bubbles: true }}));
    element.dispatchEvent(new Event("change", {{ bubbles: true }}));
  }};
  const setEditableValue = (element, value) => {{
    element.focus();
    element.innerHTML = "";
    const lines = value.split("\\n");
    lines.forEach((line, index) => {{
      if (index > 0) {{
        element.appendChild(document.createElement("br"));
      }}
      element.appendChild(document.createTextNode(line));
    }});
    element.dispatchEvent(new InputEvent("input", {{ bubbles: true, data: value, inputType: "insertText" }}));
  }};
  const candidates = Array.from(document.querySelectorAll('input, textarea, [contenteditable="true"], [role="textbox"]'))
    .filter(visible);
  const findField = (patterns, extraCheck) =>
    candidates.find((element) => {{
      const text = metaText(element);
      if (patterns.some((pattern) => pattern.test(text))) {{
        return true;
      }}
      return extraCheck ? extraCheck(element, text) : false;
    }}) || null;
  const titleField = findField([/标题/, /title/], (element) => element.tagName.toLowerCase() === "input");
  const bodyField = findField([/正文/, /内容/, /描述/, /caption/, /desc/], (element, text) => {{
    if (text.includes("title")) return false;
    return element.tagName.toLowerCase() === "textarea" || element.getAttribute("contenteditable") === "true";
  }});
  const pageText = document.body.innerText || "";
  const uploadPrompt =
    pageText.includes("上传图片") ||
    pageText.includes("上传视频") ||
    pageText.includes("文字配图") ||
    pageText.includes("上传图文") ||
    pageText.includes("选择文件");
  let filledTitle = false;
  let filledBody = false;
  if (titleField) {{
    if (titleField.getAttribute("contenteditable") === "true" || titleField.getAttribute("role") === "textbox") {{
      setEditableValue(titleField, payload.title);
    }} else {{
      setInputValue(titleField, payload.title);
    }}
    filledTitle = true;
  }}
  if (bodyField) {{
    if (bodyField.getAttribute("contenteditable") === "true" || bodyField.getAttribute("role") === "textbox") {{
      setEditableValue(bodyField, payload.body);
    }} else {{
      setInputValue(bodyField, payload.body);
    }}
    filledBody = true;
  }}
  let status = "missing_fields";
  if (filledTitle && filledBody) {{
    status = "filled";
  }} else if (!filledTitle && !filledBody && uploadPrompt) {{
    status = "awaiting_image_upload";
  }}
  return JSON.stringify({{
    status,
    filled_title: filledTitle,
    filled_body: filledBody
  }});
}})();
"""
