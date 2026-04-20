from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass


_SPLIT_MARKER = "__XIAOYAN_CHROME_CAPTURE__"
_CHROME_COPY_MARKER = "__XIAOYAN_CHROME_COPY_DONE__"
_JS_AUTOMATION_DISABLED_HINT = "通过 AppleScript 执行 JavaScript 的功能已关闭"


@dataclass(frozen=True)
class CapturedChromeTab:
    url: str
    body_text: str


def capture_active_chrome_tab() -> CapturedChromeTab:
    if sys.platform != "darwin":
        raise ValueError("xiaohongshu chrome capture currently supports macOS only")

    active_url = read_active_chrome_url()
    try:
        body_text = read_active_chrome_body_via_javascript()
    except ValueError as exc:
        if not is_javascript_for_automation_disabled(exc):
            raise
        body_text = read_active_chrome_body_via_clipboard()

    return CapturedChromeTab(url=active_url, body_text=body_text)


def read_active_chrome_url() -> str:
    output = run_osascript(
        """
tell application "Google Chrome"
    if (count of windows) is 0 then error "Google Chrome has no open windows"
    return URL of active tab of front window
end tell
"""
    )
    return output.strip()


def read_active_chrome_body_via_javascript() -> str:
    script = f"""
set outputDelimiter to "{_SPLIT_MARKER}"
tell application "Google Chrome"
    if (count of windows) is 0 then error "Google Chrome has no open windows"
    set activeTab to active tab of front window
    set activeBody to execute activeTab javascript "document.body ? document.body.innerText : ''"
    return outputDelimiter & activeBody
end tell
"""
    output = run_osascript(script)
    if _SPLIT_MARKER not in output:
        raise ValueError("unexpected Chrome capture output")
    _, body_text = output.split(_SPLIT_MARKER, 1)
    return body_text.strip()


def read_active_chrome_body_via_clipboard() -> str:
    previous_clipboard = read_clipboard_text()
    copy_script = f"""
tell application "Google Chrome" to activate
delay 0.2
tell application "System Events"
    keystroke "a" using command down
    delay 0.15
    keystroke "c" using command down
end tell
delay 0.2
return "{_CHROME_COPY_MARKER}"
"""
    try:
        output = run_osascript(copy_script)
        if output.strip() != _CHROME_COPY_MARKER:
            raise ValueError("failed to copy Chrome page content")
        body_text = read_clipboard_text().strip()
    finally:
        write_clipboard_text(previous_clipboard)
    if not body_text:
        raise ValueError("captured Chrome page content is empty")
    return body_text


def read_clipboard_text() -> str:
    completed = subprocess.run(
        ["pbpaste"],
        capture_output=True,
        text=True,
        check=False,
        timeout=5,
    )
    if completed.returncode != 0:
        return ""
    return completed.stdout


def write_clipboard_text(value: str) -> None:
    subprocess.run(
        ["pbcopy"],
        input=value,
        text=True,
        check=False,
        timeout=5,
    )


def run_osascript(script: str) -> str:
    completed = subprocess.run(
        ["osascript", "-e", script],
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    if completed.returncode != 0:
        message = (completed.stderr or completed.stdout or "").strip() or "failed to capture Chrome tab"
        raise ValueError(message)
    return completed.stdout.strip()


def is_javascript_for_automation_disabled(error: ValueError) -> bool:
    return _JS_AUTOMATION_DISABLED_HINT in str(error)
