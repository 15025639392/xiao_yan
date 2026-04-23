from __future__ import annotations

import json


def build_fill_script(*, title: str, body: str) -> str:
    payload = json.dumps({"title": title, "body": body}, ensure_ascii=False)
    return f"""
(() => {{
  try {{
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
  const candidates = Array.from(document.querySelectorAll('input, textarea, [contenteditable="true"], [role="textbox"]'))
    .filter(visible);
  const isTextboxLike = (element) => {{
    const tagName = element.tagName.toLowerCase();
    return (
      tagName === "input" ||
      tagName === "textarea" ||
      element.getAttribute("contenteditable") === "true" ||
      element.getAttribute("role") === "textbox"
    );
  }};
  const findField = (patterns, extraCheck) =>
    candidates.find((element) => {{
      const text = metaText(element);
      if (patterns.some((pattern) => pattern.test(text))) {{
        return true;
      }}
      return extraCheck ? extraCheck(element, text) : false;
    }}) || null;
  const resolveTypingTarget = (element) => {{
    if (!element) return null;
    const tagName = element.tagName.toLowerCase();
    if (
      tagName === "input" ||
      tagName === "textarea" ||
      element.getAttribute("contenteditable") === "true"
    ) {{
      return element;
    }}
    const nested = Array.from(element.querySelectorAll('input, textarea, [contenteditable="true"], [role="textbox"]'))
      .find((candidate) => visible(candidate));
    return nested || element;
  }};
  Array.from(document.querySelectorAll("[data-xiaoyan-fill-target]")).forEach((element) => {{
    element.removeAttribute("data-xiaoyan-fill-target");
  }});
  let titleField = findField([/标题/, /title/], (element, text) => {{
    if (!isTextboxLike(element)) return false;
    if (text.includes("正文") || text.includes("内容") || text.includes("描述") || text.includes("caption") || text.includes("desc")) {{
      return false;
    }}
    return element.tagName.toLowerCase() === "input";
  }});
  let bodyField = findField([/正文/, /内容/, /描述/, /caption/, /desc/], (element, text) => {{
    if (text.includes("title")) return false;
    return (
      element.tagName.toLowerCase() === "textarea" ||
      element.getAttribute("contenteditable") === "true" ||
      element.getAttribute("role") === "textbox"
    );
  }});
  if (!titleField) {{
    titleField = candidates.find((element) => {{
      if (!isTextboxLike(element)) return false;
      if (element === bodyField) return false;
      return element.tagName.toLowerCase() === "input";
    }}) || candidates.find((element) => {{
      if (!isTextboxLike(element)) return false;
      if (element === bodyField) return false;
      const text = metaText(element);
      return !(/正文|内容|描述|caption|desc/.test(text));
    }}) || null;
  }}
  if (!bodyField) {{
    bodyField = candidates.find((element) => {{
      if (!isTextboxLike(element)) return false;
      if (element === titleField) return false;
      return (
        element.tagName.toLowerCase() === "textarea" ||
        element.getAttribute("contenteditable") === "true" ||
        element.getAttribute("role") === "textbox"
      );
    }}) || null;
  }}
  const titleTarget = resolveTypingTarget(titleField);
  const bodyTarget = resolveTypingTarget(bodyField);
  if (titleTarget) {{
    titleTarget.setAttribute("data-xiaoyan-fill-target", "title");
  }}
  if (bodyTarget) {{
    bodyTarget.setAttribute("data-xiaoyan-fill-target", "body");
  }}
  const pageText = document.body.innerText || "";
  const uploadPrompt =
    pageText.includes("上传图片") ||
    pageText.includes("上传视频") ||
    pageText.includes("上传图文") ||
    pageText.includes("选择文件");
  let filledTitle = false;
  let filledBody = false;
  if (titleTarget) {{
    if (
      titleTarget.tagName.toLowerCase() === "input" ||
      titleTarget.tagName.toLowerCase() === "textarea"
    ) {{
      setInputValue(titleTarget, payload.title);
      filledTitle = true;
    }} else if (
      titleTarget.getAttribute("contenteditable") === "true" ||
      titleTarget.getAttribute("role") === "textbox"
    ) {{
      filledTitle = false;
    }} else {{
      setInputValue(titleTarget, payload.title);
      filledTitle = true;
    }}
  }}
  if (bodyTarget) {{
    if (bodyTarget.tagName.toLowerCase() === "textarea") {{
      setInputValue(bodyTarget, payload.body);
      filledBody = true;
    }} else if (bodyTarget.getAttribute("contenteditable") === "true" || bodyTarget.getAttribute("role") === "textbox") {{
      filledBody = false;
    }} else {{
      setInputValue(bodyTarget, payload.body);
      filledBody = true;
    }}
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
  }} catch(err) {{
    return JSON.stringify({{
      status: "js_error",
      filled_title: false,
      filled_body: false,
      error: String(err && err.message ? err.message : err)
    }});
  }}
}})();
"""
