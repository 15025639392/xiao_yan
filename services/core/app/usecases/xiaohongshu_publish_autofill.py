from __future__ import annotations

import json

from app.api.platform_route_models import XiaohongshuPublishAutofillResponse
from app.api.tool_capability_bridge import (
    BrowserCapabilityError,
    BrowserOrganUnavailable,
    call_browser_capability,
)


_PUBLISH_URL = "https://creator.xiaohongshu.com/publish/publish?from=xiao_yan&target=image"


def _build_fill_script(*, title: str, body: str) -> str:
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
}})();
"""


def autofill_xiaohongshu_publish_page(
    *,
    title: str,
    body: str,
    auto_publish: bool = False,
    publish_selector: str = "",
) -> XiaohongshuPublishAutofillResponse:
    """Auto-fill the Xiaohongshu publish page.

    Args:
        title: Title text
        body: Body/description text
        auto_publish: If True, also click the publish button after filling
        publish_selector: CSS selector for the publish button (required if auto_publish=True)
    """
    normalized_title = title.strip()
    normalized_body = body.strip()
    if not normalized_title:
        raise ValueError("publish title cannot be blank")
    if not normalized_body:
        raise ValueError("publish body cannot be blank")

    if auto_publish and not publish_selector:
        return _fallback_response("missing_selector", "auto_publish requires publish_selector")

    # 1. Open publish page via browser organ
    try:
        open_result = call_browser_capability(
            "browser.open",
            {"url": _PUBLISH_URL, "headless": False},
            timeout_seconds=15.0,
        )
    except BrowserOrganUnavailable:
        return _fallback_response("browser_unavailable", "浏览器器官不可用，请手动打开发布页")

    session_id = open_result.get("session_id")
    if not session_id:
        return _fallback_response("open_failed", "打开发布页失败")

    # 2. Fill and optionally click publish via browser.publish capability
    try:
        publish_result = call_browser_capability(
            "browser.publish",
            {
                "session_id": session_id,
                "title": normalized_title,
                "body": normalized_body,
                "publish_selector": publish_selector if auto_publish else "",
            },
            timeout_seconds=20.0,
        )
    except BrowserCapabilityError as exc:
        _ensure_close(session_id)
        return _fallback_response("publish_failed", f"发布失败: {exc}")
    finally:
        _ensure_close(session_id)

    # 3. Parse and return
    status = str(publish_result.get("status", "filled"))
    filled_title = bool(publish_result.get("filled_title", False))
    filled_body = bool(publish_result.get("filled_body", False))
    publish_clicked = bool(publish_result.get("publish_clicked", False))
    message = _build_result_message(
        status=status,
        filled_title=filled_title,
        filled_body=filled_body,
        publish_clicked=publish_clicked,
        auto_publish=auto_publish,
    )
    return XiaohongshuPublishAutofillResponse(
        status=status,
        publish_url=_PUBLISH_URL,
        title=normalized_title,
        body=normalized_body,
        filled_title=filled_title,
        filled_body=filled_body,
        message=message,
    )


def _ensure_close(session_id: str) -> None:
    """Ensure browser session is closed."""
    try:
        call_browser_capability(
            "browser.close",
            {"session_id": session_id},
            timeout_seconds=5.0,
        )
    except Exception:
        pass


def _fallback_response(status: str, message: str) -> XiaohongshuPublishAutofillResponse:
    """Return a fallback response when browser organ fails."""
    return XiaohongshuPublishAutofillResponse(
        status=status,
        publish_url=_PUBLISH_URL,
        title="",
        body="",
        filled_title=False,
        filled_body=False,
        message=message,
    )


def _build_result_message(
    *,
    status: str,
    filled_title: bool,
    filled_body: bool,
    publish_clicked: bool = False,
    auto_publish: bool = False,
) -> str:
    if auto_publish and publish_clicked:
        return "已自动打开发布页、填入草稿并点击发布按钮。"
    if status == "filled":
        return "已打开发布页，并把标题和正文草稿填进当前图文发布表单。"
    if status == "awaiting_image_upload":
        return "已打开发布页，但当前还在素材上传前置步骤。请先切到图文并上传首图，再点一次自动填充。"
    if status == "missing_fields":
        if filled_title or filled_body:
            return "已部分填充发布页字段，剩余字段需要你手动补一下。"
        return "已打开发布页，但暂时没识别到标题和正文输入区。"
    return "已打开小红书发布页。"
