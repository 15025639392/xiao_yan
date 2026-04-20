from __future__ import annotations

import json
import subprocess
import sys
import time

from app.api.platform_route_models import XiaohongshuPublishAutofillResponse


_PUBLISH_URL = "https://creator.xiaohongshu.com/publish/publish?from=xiao_yan&target=image"
_JS_AUTOMATION_DISABLED_HINT = "通过 AppleScript 执行 JavaScript 的功能已关闭"


def autofill_xiaohongshu_publish_page(*, title: str, body: str) -> XiaohongshuPublishAutofillResponse:
    normalized_title = title.strip()
    normalized_body = body.strip()
    if not normalized_title:
        raise ValueError("publish title cannot be blank")
    if not normalized_body:
        raise ValueError("publish body cannot be blank")
    if sys.platform != "darwin":
        raise ValueError("xiaohongshu publish autofill currently supports macOS only")

    _open_chrome_publish_page()
    time.sleep(0.8)

    try:
        raw_result = _run_fill_script_with_retry(title=normalized_title, body=normalized_body)
    except ValueError as exc:
        if _JS_AUTOMATION_DISABLED_HINT not in str(exc):
            raise
        return XiaohongshuPublishAutofillResponse(
            status="opened_publish_page",
            publish_url=_PUBLISH_URL,
            title=normalized_title,
            body=normalized_body,
            filled_title=False,
            filled_body=False,
            message="已打开小红书发布页，但 Chrome 未开启 AppleScript JavaScript，当前改为手动粘贴。",
        )

    try:
        payload = json.loads(raw_result)
    except json.JSONDecodeError as exc:
        raise ValueError("unexpected xiaohongshu publish autofill result") from exc

    status = str(payload.get("status") or "opened_publish_page")
    filled_title = bool(payload.get("filled_title"))
    filled_body = bool(payload.get("filled_body"))
    message = _build_result_message(status=status, filled_title=filled_title, filled_body=filled_body)
    return XiaohongshuPublishAutofillResponse(
        status=status,
        publish_url=_PUBLISH_URL,
        title=normalized_title,
        body=normalized_body,
        filled_title=filled_title,
        filled_body=filled_body,
        message=message,
    )


def _build_result_message(*, status: str, filled_title: bool, filled_body: bool) -> str:
    if status == "filled":
        return "已打开发布页，并把标题和正文草稿填进当前图文发布表单。"
    if status == "awaiting_image_upload":
        return "已打开发布页，但当前还在素材上传前置步骤。请先切到图文并上传首图，再点一次自动填充。"
    if status == "missing_fields":
        if filled_title or filled_body:
            return "已部分填充发布页字段，剩余字段需要你手动补一下。"
        return "已打开发布页，但暂时没识别到标题和正文输入区。"
    return "已打开小红书发布页。"


def _run_fill_script_with_retry(*, title: str, body: str) -> str:
    script = _build_fill_script(title=title, body=body)
    last_result = ""
    for attempt in range(3):
        last_result = _execute_active_tab_javascript(script)
        if '"status":"missing_fields"' not in last_result.replace(" ", ""):
            return last_result
        if attempt < 2:
            time.sleep(0.6)
    return last_result


def _open_chrome_publish_page() -> None:
    _run_osascript(
        f"""
tell application "Google Chrome"
    activate
    if (count of windows) is 0 then
        make new window
    end if
    set URL of active tab of front window to "{_PUBLISH_URL}"
end tell
"""
    )


def _execute_active_tab_javascript(script: str) -> str:
    escaped_script = _to_applescript_string(script)
    return _run_osascript(
        f"""
tell application "Google Chrome"
    if (count of windows) is 0 then error "Google Chrome has no open windows"
    set activeTab to active tab of front window
    return execute activeTab javascript {escaped_script}
end tell
"""
    )


def _run_osascript(script: str) -> str:
    completed = subprocess.run(
        ["osascript", "-e", script],
        capture_output=True,
        text=True,
        check=False,
        timeout=15,
    )
    if completed.returncode != 0:
        message = (completed.stderr or completed.stdout or "").strip() or "failed to control Chrome"
        raise ValueError(message)
    return completed.stdout.strip()


def _to_applescript_string(value: str) -> str:
    escaped = (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\r", "\\r")
        .replace("\n", "\\n")
    )
    return f'"{escaped}"'


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
