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
  const createParagraphNodes = (value) => {{
    const fragment = document.createDocumentFragment();
    const blocks = value.split(/\\n\\s*\\n/);
    blocks.forEach((block) => {{
      const paragraph = document.createElement("p");
      const lines = block.split("\\n");
      lines.forEach((line, index) => {{
        if (index > 0) {{
          paragraph.appendChild(document.createElement("br"));
        }}
        if (line) {{
          paragraph.appendChild(document.createTextNode(line));
        }}
      }});
      if (!paragraph.childNodes.length) {{
        paragraph.appendChild(document.createElement("br"));
      }}
      fragment.appendChild(paragraph);
    }});
    if (!fragment.childNodes.length) {{
      const paragraph = document.createElement("p");
      paragraph.appendChild(document.createElement("br"));
      fragment.appendChild(paragraph);
    }}
    return fragment;
  }};
  const setEditableValue = (element, value, options = {{}}) => {{
    const multiline = Boolean(options.multiline);
    element.focus();
    element.innerHTML = "";
    if (multiline) {{
      element.appendChild(createParagraphNodes(value));
    }} else {{
      element.appendChild(document.createTextNode(value));
    }}
    Array.from(element.querySelectorAll(".is-empty, .is-editor-empty")).forEach((node) => {{
      node.classList.remove("is-empty");
      node.classList.remove("is-editor-empty");
    }});
    element.dispatchEvent(new InputEvent("beforeinput", {{ bubbles: true, data: value, inputType: multiline ? "insertParagraph" : "insertText" }}));
    element.dispatchEvent(new InputEvent("input", {{ bubbles: true, data: value, inputType: multiline ? "insertParagraph" : "insertText" }}));
    element.dispatchEvent(new Event("change", {{ bubbles: true }}));
    element.dispatchEvent(new Event("blur", {{ bubbles: true }}));
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
      setEditableValue(titleField, payload.title, {{ multiline: false }});
    }} else {{
      setInputValue(titleField, payload.title);
    }}
    filledTitle = true;
  }}
  if (bodyField) {{
    if (bodyField.getAttribute("contenteditable") === "true" || bodyField.getAttribute("role") === "textbox") {{
      setEditableValue(bodyField, payload.body, {{ multiline: true }});
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
