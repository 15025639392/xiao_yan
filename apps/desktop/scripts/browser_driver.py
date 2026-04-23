#!/usr/bin/env python3
"""
Browser capability driver daemon.
Daemon mode: python browser_driver.py daemon <socket_path>
Proxy mode:  python browser_driver.py <action> <json_args>

All Playwright operations run on a single dedicated thread owned by the daemon,
avoiding cross-thread Playwright API calls.
"""

from __future__ import annotations

import json
import os
import re
import socket
import subprocess
import sys
import threading
import queue
import time
from datetime import datetime, timezone
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

from browser_driver_runtime import launch_browser_organ_persistent_context
from browser_driver_profile import ensure_browser_organ_chrome_running, resolve_browser_cdp_endpoint
from browser_driver_result_parser import parse_evaluate_result
from browser_driver_scripts import build_fill_script


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class BrowserSession:
    def __init__(self, session_id: str, browser, context, page):
        self.session_id = session_id
        self.browser = browser
        self.context = context
        self.page = page
        self.created_at = now_iso()


class DriverDaemon:
    def __init__(self, socket_path: str):
        self.socket_path = socket_path
        self.sessions: dict[str, BrowserSession] = {}
        self._request_queue: queue.Queue = queue.Queue()
        self._result_map: dict[int, dict] = {}
        self._result_lock = threading.Lock()
        self._seq = 0
        self._worker_thread: threading.Thread | None = None
        self._running = True
        # Prefer reusing browser state instead of cold-booting a fresh session each time.
        self._cdp_browser = None  # type: ignore
        self._cdp_context = None  # type: ignore
        self._persistent_context = None  # type: ignore

    def _run_worker(self) -> None:
        """Single thread for all Playwright operations."""
        from playwright.sync_api import sync_playwright, Error as PlaywrightError

        pw = sync_playwright().start()
        try:
            while self._running:
                try:
                    seq, action, args = self._request_queue.get(timeout=0.5)
                except queue.Empty:
                    continue

                result: dict[str, Any]
                error: str | None = None
                try:
                    if action == "open":
                        result = self._cmd_open(args, pw)
                    elif action == "snapshot":
                        result = self._cmd_snapshot(args)
                    elif action == "extract":
                        result = self._cmd_extract(args)
                    elif action == "close":
                        result = self._cmd_close(args)
                    elif action == "fill_form":
                        result = self._cmd_fill_form(args)
                    elif action == "click_element":
                        result = self._cmd_click_element(args)
                    elif action == "publish":
                        result = self._cmd_publish(args)
                    elif action == "find_publish_button":
                        result = self._cmd_find_publish_button(args)
                    elif action == "evaluate":
                        result = self._cmd_evaluate(args)
                    elif action == "ping":
                        result = {"status": "ok", "socket_path": self.socket_path}
                    else:
                        result = {}
                except Exception as exc:
                    error = str(exc)
                    result = {}

                resp = {"ok": error is None, "error": error, "result": result}
                with self._result_lock:
                    self._result_map[seq] = resp
        finally:
            try:
                pw.stop()
            except Exception:
                pass

    def _enqueue_request(self, action: str, args: dict) -> dict:
        with self._result_lock:
            seq = self._seq
            self._result_map[seq] = None
            self._seq += 1

        self._request_queue.put((seq, action, args))

        # Wait for result
        while True:
            with self._result_lock:
                resp = self._result_map.get(seq)
            if resp is not None:
                with self._result_lock:
                    del self._result_map[seq]
                return resp
            threading.Event().wait(0.05)

    def cmd_open(self, args: dict) -> dict:
        """Thread-safe: enqueues to worker thread."""
        return self._enqueue_request("open", args)

    def cmd_snapshot(self, args: dict) -> dict:
        return self._enqueue_request("snapshot", args)

    def cmd_extract(self, args: dict) -> dict:
        return self._enqueue_request("extract", args)

    def cmd_close(self, args: dict) -> dict:
        return self._enqueue_request("close", args)

    def cmd_shutdown(self, _args: dict) -> dict:
        """Shut down the daemon gracefully."""
        self._running = False
        # Close all browser sessions
        for session in list(self.sessions.values()):
            try:
                if session.browser is not None:
                    session.browser.close()
                else:
                    session.context.close()
            except Exception:
                pass
        if self._persistent_context is not None:
            try:
                self._persistent_context.close()
            except Exception:
                pass
            self._persistent_context = None
        self.sessions.clear()
        return {"ok": True}

    # --- Commands run on worker thread (no GIL issues) ---

    def _cmd_open(self, args: dict, pw) -> dict:
        url = args["url"]
        session_id = args.get("session_id") or f"browser-{os.urandom(8).hex()}"
        headless = args.get("headless", True)
        wait_until = args.get("wait_until", "domcontentloaded")
        activate = args.get("activate", True)

        reused = self._reuse_existing_session(session_id, url, wait_until=wait_until, activate=activate)
        if reused is not None:
            return reused

        # Try to reuse an existing Chrome via CDP (preserves cookies / login session)
        cdp_browser = self._try_connect_existing_chrome(pw)
        if cdp_browser is not None:
            self._cdp_browser = cdp_browser
            self._cdp_context = self._wait_for_cdp_context(cdp_browser)
            try:
                page = self._prepare_page(self._cdp_context, url)
                self._activate_page(page, url, wait_until=wait_until, activate=activate)
                usable, reason = self._is_page_usable(page, url)
                if not usable:
                    raise RuntimeError(f"page unusable after CDP navigation: {reason}")
                self.sessions[session_id] = BrowserSession(session_id, self._cdp_browser, self._cdp_context, page)
                return {
                    "session_id": session_id,
                    "url": url,
                    "resolved_url": page.url,
                    "title": page.title(),
                    "status": "active",
                    "opened_at": now_iso(),
                }
            except Exception:
                # CDP reuse failed, fall through to fresh launch
                try:
                    cdp_browser.close()
                except Exception:
                    pass
                self._cdp_browser = None
                self._cdp_context = None

        if self._persistent_context is not None:
            try:
                page = self._prepare_page(self._persistent_context, url)
                self._activate_page(page, url, wait_until=wait_until, activate=activate)
                usable, reason = self._is_page_usable(page, url)
                if not usable:
                    raise RuntimeError(f"page unusable after persistent context navigation: {reason}")
                self.sessions[session_id] = BrowserSession(session_id, None, self._persistent_context, page)
                return {
                    "session_id": session_id,
                    "url": url,
                    "resolved_url": page.url,
                    "title": page.title(),
                    "status": "active",
                    "opened_at": now_iso(),
                }
            except Exception:
                try:
                    self._persistent_context.close()
                except Exception:
                    pass
                self._persistent_context = None

        try:
            persistent_context = launch_browser_organ_persistent_context(pw, headless=headless)
        except Exception:
            persistent_context = None

        if persistent_context is not None:
            self._persistent_context = persistent_context
            page = self._prepare_page(persistent_context, url)
            try:
                self._activate_page(page, url, wait_until=wait_until, activate=activate)
                usable, reason = self._is_page_usable(page, url)
                if not usable:
                    raise RuntimeError(f"page unusable after launch navigation: {reason}")
            except Exception as exc:
                try:
                    persistent_context.close()
                except Exception:
                    pass
                self._persistent_context = None
                raise RuntimeError(f"navigation failed: {exc}")

            self.sessions[session_id] = BrowserSession(session_id, None, persistent_context, page)
            return {
                "session_id": session_id,
                "url": url,
                "resolved_url": page.url,
                "title": page.title(),
                "status": "active",
                "opened_at": now_iso(),
            }

        ensure_browser_organ_chrome_running()
        cdp_browser = self._try_connect_existing_chrome(pw)
        if cdp_browser is None:
            raise RuntimeError("browser organ chrome did not expose a reusable cdp endpoint")

        context = self._wait_for_cdp_context(cdp_browser)
        browser = cdp_browser
        page = self._prepare_page(context, url)

        try:
            self._activate_page(page, url, wait_until=wait_until, activate=activate)
            usable, reason = self._is_page_usable(page, url)
            if not usable:
                raise RuntimeError(f"page unusable after CDP fresh navigation: {reason}")
        except Exception as exc:
            raise RuntimeError(f"navigation failed: {exc}")

        self.sessions[session_id] = BrowserSession(session_id, browser, context, page)
        self._cdp_browser = browser
        self._cdp_context = context

        return {
            "session_id": session_id,
            "url": url,
            "resolved_url": page.url,
            "title": page.title(),
            "status": "active",
            "opened_at": now_iso(),
        }

    def _try_connect_existing_chrome(self, pw) -> Any | None:
        """Try to connect to an already-running Chrome via CDP."""
        try:
            cdp_endpoint = resolve_browser_cdp_endpoint()
            if not cdp_endpoint:
                return None
            return pw.chromium.connect_over_cdp(cdp_endpoint)
        except Exception:
            return None

    def _wait_for_cdp_context(self, browser):
        for _ in range(30):
            contexts = list(browser.contexts)
            if contexts:
                return contexts[0]
            threading.Event().wait(0.1)
        raise RuntimeError("cdp browser exposed no reusable context")

    def _prepare_page(self, context, url: str):
        page = self._find_reusable_page(context, url)
        if page is not None:
            return page

        page = self._pick_fallback_page(context)
        if page is not None:
            return page

        return context.new_page()

    def _reuse_existing_session(
        self,
        session_id: str,
        url: str,
        *,
        wait_until: str,
        activate: bool,
    ) -> dict[str, Any] | None:
        session = self.sessions.get(session_id)
        if session is None:
            return None

        try:
            resolved = self._resolve_session(session_id)
        except Exception:
            self.sessions.pop(session_id, None)
            return None

        page = resolved.page
        self._activate_page(page, url, wait_until=wait_until, activate=activate)
        return {
            "session_id": session_id,
            "url": url,
            "resolved_url": page.url,
            "title": page.title(),
            "status": "active",
            "opened_at": now_iso(),
        }

    def _find_reusable_page(self, context, url: str):
        for page in reversed(list(context.pages)):
            try:
                if self._matches_requested_location(page.url, url):
                    return page
            except Exception:
                continue
        return None

    def _pick_fallback_page(self, context):
        pages = list(context.pages)
        for page in reversed(pages):
            try:
                if self._is_reusable_page_url(page.url):
                    return page
            except Exception:
                continue
        return pages[-1] if pages else None

    def _activate_page(self, page, url: str, *, wait_until: str, activate: bool) -> None:
        if not self._matches_requested_location(page.url, url):
            page.goto(url, wait_until=wait_until, timeout=15000)
        if activate:
            try:
                page.bring_to_front()
            except Exception:
                pass

    def _is_page_usable(self, page, url: str) -> tuple[bool, str]:
        """Check if page is usable for the requested URL. Returns (usable, reason)."""
        try:
            current = page.url
        except Exception as exc:
            return False, f"cannot read page URL: {exc}"
        if not current or current == "about:blank":
            return False, f"page is blank after navigation to {url}"
        if current.startswith(("chrome://", "devtools://", "chrome-extension://")):
            return False, f"page navigated to internal URL: {current}"
        return True, ""

    def _matches_requested_location(self, current_url: str, requested_url: str) -> bool:
        if not current_url or not requested_url:
            return False
        normalized_current = current_url.rstrip("/")
        normalized_requested = requested_url.rstrip("/")
        if normalized_current == normalized_requested:
            return True
        if normalized_current.startswith(normalized_requested):
            return True
        if self._is_login_redirect_for_requested_url(current_url, requested_url):
            return True
        return False

    def _is_reusable_page_url(self, url: str) -> bool:
        if not url or url == "about:blank":
            return False
        return not url.startswith(("chrome://", "devtools://", "chrome-extension://"))

    def _is_login_redirect_for_requested_url(self, current_url: str, requested_url: str) -> bool:
        try:
            current = urlparse(current_url)
            requested = urlparse(requested_url)
        except Exception:
            return False

        if not current.netloc or current.netloc != requested.netloc:
            return False
        if current.path != "/login":
            return False

        last_urls = parse_qs(current.query).get("lastUrl", [])
        requested_path = requested.path.rstrip("/")
        for raw_last_url in last_urls:
            decoded_last_url = self._fully_unquote(raw_last_url).strip()
            if not decoded_last_url:
                continue

            if decoded_last_url.startswith("http://") or decoded_last_url.startswith("https://"):
                target = urlparse(decoded_last_url)
            else:
                target = urlparse(f"{requested.scheme}://{requested.netloc}{decoded_last_url}")

            if target.netloc and target.netloc != requested.netloc:
                continue

            target_path = target.path.rstrip("/")
            if not target_path:
                continue
            if target_path == requested_path or requested_path.startswith(target_path):
                return True
        return False

    def _fully_unquote(self, value: str) -> str:
        decoded = value
        for _ in range(3):
            next_decoded = unquote(decoded)
            if next_decoded == decoded:
                break
            decoded = next_decoded
        return decoded

    def _cmd_snapshot(self, args: dict) -> dict:
        session_id = args["session_id"]
        include_text = args.get("include_text", True)
        include_accessibility = args.get("include_accessibility", False)
        include_screenshot = args.get("include_screenshot", False)
        max_text_bytes = args.get("max_text_bytes")
        if not isinstance(max_text_bytes, int) or max_text_bytes <= 0:
            max_text_bytes = 512 * 1024

        session = self._resolve_session(session_id)
        page = session.page
        captured_at = now_iso()
        url = page.url
        title = page.title()

        text_content = ""
        if include_text:
            try:
                raw = page.inner_text("body")
            except Exception:
                raw = ""
            enc = raw.encode("utf-8")
            if len(enc) > max_text_bytes:
                raw = enc[:max_text_bytes].decode("utf-8", errors="replace")
            text_content = raw

        accessibility_tree = None
        if include_accessibility:
            try:
                accessibility_tree = page.accessibility.snapshot()
            except Exception:
                pass

        screenshot_path = None
        if include_screenshot:
            try:
                tmp = os.path.join(os.getenv("TMPDIR") or "/tmp", f"snap-{session_id[:12]}.png")
                page.screenshot(path=tmp)
                screenshot_path = tmp
            except Exception:
                pass

        return {
            "session_id": session_id,
            "url": url,
            "title": title,
            "text_content": text_content,
            "accessibility_tree": accessibility_tree,
            "screenshot_path": screenshot_path,
            "captured_at": captured_at,
        }

    def _cmd_extract(self, args: dict) -> dict:
        session_id = args["session_id"]
        target = args["target"]
        schema = args.get("schema")
        max_items = args.get("max_items", 50)

        session = self._resolve_session(session_id)
        page = session.page
        captured_at = now_iso()
        source_url = page.url

        try:
            elements = page.query_selector_all(target)
            items: list[dict[str, Any]] = []
            for el in elements[:max_items]:
                item: dict[str, Any] = {"tag": el.evaluate("el => el.tagName") if el else ""}
                try:
                    item["text"] = el.inner_text() if el else ""
                except Exception:
                    item["text"] = ""
                try:
                    item["href"] = el.get_attribute("href") if el else None
                except Exception:
                    item["href"] = None
                items.append(item)

            content = "\n".join(i.get("text", "") or "" for i in items)
            structured_data: Any = items
            if schema:
                fields = schema.get("fields", []) if isinstance(schema, dict) else []
                if fields:
                    structured_data = [{k: i.get(k) for k in fields if k in i} for i in items]
                else:
                    structured_data = items

            return {
                "session_id": session_id,
                "target": target,
                "content": content,
                "structured_data": structured_data,
                "source_url": source_url,
                "captured_at": captured_at,
            }
        except Exception as exc:
            return {
                "session_id": session_id,
                "target": target,
                "content": "",
                "structured_data": None,
                "source_url": source_url,
                "captured_at": captured_at,
                "last_error": str(exc),
            }

    def _cmd_close(self, args: dict) -> dict:
        session_id = args["session_id"]
        session = self.sessions.pop(session_id, None)
        if session:
            try:
                # Only close the page — preserve the browser process and CDP connection
                # so cookies/login state survive across scouting cycles.
                session.page.close()
            except Exception:
                pass
        return {
            "session_id": session_id,
            "closed_at": now_iso(),
            "status": "closed",
        }

    def _resolve_session(self, session_id: str) -> BrowserSession:
        session = self.sessions.get(session_id)
        if session is None:
            raise ValueError(f"session not found: {session_id}")
        browser = session.context.browser
        if browser is not None and browser.is_connected() is False:
            raise ValueError(f"session browser disconnected: {session_id}")
        if session.page.is_closed():
            raise ValueError(f"session page closed: {session_id}")
        return session

    # ── evaluate ─────────────────────────────────────────────────────────────

    def cmd_evaluate(self, args: dict) -> dict:
        return self._enqueue_request("evaluate", args)

    def _cmd_evaluate(self, args: dict) -> dict:
        session_id = args["session_id"]
        script = args.get("script", "")
        if not script:
            raise ValueError("script is required")

        session = self._resolve_session(session_id)
        result = session.page.evaluate(script)
        return {
            "session_id": session_id,
            "result": result,
            "evaluated_at": now_iso(),
        }

    # ── fill_form ────────────────────────────────────────────────────────────

    def cmd_fill_form(self, args: dict) -> dict:
        """Thread-safe: enqueues to worker thread."""
        return self._enqueue_request("fill_form", args)

    def _cmd_fill_form(self, args: dict) -> dict:
        session_id = args["session_id"]
        title = args.get("title", "")
        body = args.get("body", "")

        session = self._resolve_session(session_id)
        page = session.page

        script = build_fill_script(title=title, body=body)
        try:
            raw_result = page.evaluate(script)
        except Exception as exc:
            return {
                "session_id": session_id,
                "status": "page_error",
                "filled_title": False,
                "filled_body": False,
                "error": str(exc),
            }
        try:
            parsed_result = parse_evaluate_result(raw_result)
        except ValueError as exc:
            return {
                "session_id": session_id,
                "status": "page_error",
                "filled_title": False,
                "filled_body": False,
                "error": str(exc),
            }
        return {
            "session_id": session_id,
            "status": parsed_result.get("status", "unknown"),
            "filled_title": parsed_result.get("filled_title", False),
            "filled_body": parsed_result.get("filled_body", False),
        }

    # ── click_element ────────────────────────────────────────────────────────

    def cmd_click_element(self, args: dict) -> dict:
        """Thread-safe: enqueues to worker thread."""
        return self._enqueue_request("click_element", args)

    def _cmd_click_element(self, args: dict) -> dict:
        session_id = args["session_id"]
        selector = args.get("selector", "")
        if not selector:
            raise ValueError("selector is required for click_element")

        session = self._resolve_session(session_id)
        page = session.page

        try:
            page.click(selector, timeout=10000)
            return {
                "session_id": session_id,
                "status": "clicked",
                "selector": selector,
                "clicked": True,
            }
        except Exception as exc:
            return {
                "session_id": session_id,
                "status": "click_failed",
                "selector": selector,
                "clicked": False,
                "error": str(exc),
            }

    # ── publish ───────────────────────────────────────────────────────────────

    def cmd_publish(self, args: dict) -> dict:
        """Thread-safe: enqueues to worker thread."""
        return self._enqueue_request("publish", args)

    def _cmd_publish(self, args: dict) -> dict:
        session_id = args.get("session_id") if isinstance(args, dict) else str(args)
        title = args.get("title", "") if isinstance(args, dict) else ""
        body = args.get("body", "") if isinstance(args, dict) else ""
        publish_selector = args.get("publish_selector", "") if isinstance(args, dict) else ""
        image_paths = args.get("image_paths", []) if isinstance(args, dict) else []

        def _log(msg: str) -> None:
            print(f"[publish {session_id[:8]}] {msg}", flush=True)

        _log(f"starting: images={len(image_paths) if isinstance(image_paths, list) else 0}, title={repr(title[:20])}, body={repr(body[:30])}")

        try:
            session = self._resolve_session(session_id)
        except Exception as exc:
            _log(f"session error: {exc}")
            return self._publish_result(
                session_id=session_id,
                status="session_error",
                error=f"session error: {exc}",
            )

        try:
            page = getattr(session, "page", None)
            if page is None:
                _log("session.page is None")
                return self._publish_result(session_id=session_id, status="session_error", error="session.page is None")
            if page.is_closed():
                _log("page is closed")
                return self._publish_result(session_id=session_id, status="page_closed", error="page is closed")
            current_url = page.url
            if not current_url or current_url.startswith(("chrome://", "devtools://", "about:")):
                _log(f"invalid page URL: {current_url}")
                return self._publish_result(session_id=session_id, status="page_error", error=f"invalid URL: {current_url}")
            _log(f"page URL: {current_url}")
        except Exception as exc:
            _log(f"page access error: {exc}")
            return self._publish_result(session_id=session_id, status="page_error", error=f"page access error: {exc}")

        uploaded_image_count = 0
        upload_error: str | None = None
        images_already_on_page = False

        if isinstance(image_paths, list) and image_paths:
            _log(f"uploading {len(image_paths)} image(s)")
            try:
                uploaded_image_count = self._set_publish_images(page, image_paths)
                _log(f"upload returned: {uploaded_image_count}")
            except Exception as exc:
                upload_error = str(exc)
                _log(f"upload error: {exc}")
        elif isinstance(image_paths, list) and not image_paths:
            # No image_paths provided — check if images are already on the page
            try:
                existing = page.evaluate(
                    "(function(){"
                    "const imgs=document.querySelectorAll('img');"
                    "return imgs.length;"
                    "})()",
                    timeout=3000,
                )
                images_already_on_page = isinstance(existing, (int, float)) and existing > 0
                if images_already_on_page:
                    _log(f"no image_paths given, but {existing} images already on page")
            except Exception:
                pass

        script = build_fill_script(title=title, body=body)

        # After upload, wait for the page to transition from "upload state" to "form state".
        # The upload triggers a DOM re-render. Poll until upload prompts disappear.
        if uploaded_image_count > 0 or images_already_on_page:
            _log("waiting for form to appear after image upload")
            form_ready = False
            for poll in range(8):
                try:
                    page.wait_for_timeout(2000)
                    body_text = page.inner_text("body", timeout=3000).lower()
                    # Check if upload prompts are gone (form state reached)
                    upload_prompts = any(
                        kw in body_text for kw in ["上传图片", "上传视频", "上传图文", "选择文件", "拖拽上传"]
                    )
                    if not upload_prompts:
                        _log(f"form ready after {poll + 1} polls (upload prompts gone)")
                        form_ready = True
                        break
                    _log(f"poll {poll + 1}: still showing upload prompts, waiting...")
                except Exception as poll_exc:
                    _log(f"poll {poll + 1} failed: {poll_exc}")
                    break
            if not form_ready:
                _log("form did not appear after 8 polls — proceeding anyway")

        fill_result: dict = {}
        fill_error: str | None = None

        # Verify page is alive before attempting fill
        try:
            _ = page.inner_text("body", timeout=3000)
        except Exception as exc:
            _log(f"page dead before fill: {exc}")
            return self._publish_result(
                session_id=session_id,
                status="page_error",
                filled_title=False,
                filled_body=False,
                uploaded_image_count=uploaded_image_count,
                upload_error=upload_error,
                error=f"page dead before fill: {exc}",
            )

        def _run_fill() -> dict:
            try:
                raw = page.evaluate(script)
                return parse_evaluate_result(raw)
            except Exception as exc:
                raise RuntimeError(f"fill evaluate failed: {exc}")

        # Try fill with up to 2 retries. "awaiting_image_upload" means the page is still
        # in upload state (transition not complete yet). Wait and retry.
        for attempt in range(3):
            try:
                fill_result = _run_fill()
                status_val = fill_result.get("status", "") if isinstance(fill_result, dict) else ""
                _log(f"fill attempt {attempt + 1}: {fill_result}")

                if status_val == "awaiting_image_upload" and attempt < 2:
                    _log("form not ready yet, waiting 3s and retrying...")
                    try:
                        page.wait_for_timeout(3000)
                    except Exception:
                        pass
                    continue

                # Success or non-retryable status
                break
            except RuntimeError as exc:
                _log(f"fill attempt {attempt + 1} error: {exc}")
                fill_error = str(exc)
                if attempt < 2:
                    try:
                        page.wait_for_timeout(2000)
                    except Exception:
                        pass
                    continue
                fill_result = {}

        # Click publish button if selector provided
        clicked = False
        click_error: str | None = None
        if publish_selector and fill_result.get("filled_title") and fill_result.get("filled_body"):
            _log(f"clicking publish button: {publish_selector}")
            try:
                page.click(publish_selector, timeout=10000)
                clicked = True
            except Exception as exc:
                click_error = str(exc)
                _log(f"publish click error: {exc}")

        status = fill_result.get("status", "unknown") if isinstance(fill_result, dict) else "unknown"
        if fill_error and not isinstance(fill_result, dict):
            status = "fill_error"

        _log(f"done: status={status}, filled_title={fill_result.get('filled_title', False)}, filled_body={fill_result.get('filled_body', False)}, error={fill_error}")
        return self._publish_result(
            session_id=session_id,
            status=status,
            filled_title=fill_result.get("filled_title", False) if isinstance(fill_result, dict) else False,
            filled_body=fill_result.get("filled_body", False) if isinstance(fill_result, dict) else False,
            publish_clicked=clicked,
            click_error=click_error,
            uploaded_image_count=uploaded_image_count,
            upload_error=upload_error,
            error=fill_error,
        )

    def _publish_result(
        self,
        session_id: str,
        status: str,
        filled_title: bool = False,
        filled_body: bool = False,
        publish_clicked: bool = False,
        click_error: str | None = None,
        uploaded_image_count: int = 0,
        upload_error: str | None = None,
        error: str | None = None,
    ) -> dict:
        result = {
            "session_id": session_id,
            "filled_title": filled_title,
            "filled_body": filled_body,
            "status": status,
            "publish_clicked": publish_clicked,
            "click_error": click_error,
            "uploaded_image_count": uploaded_image_count,
            "upload_error": upload_error,
        }
        if error is not None:
            result["error"] = error
        return result

    def _set_publish_images(self, page, image_paths: list[str]) -> int:
        normalized = [str(item).strip() for item in image_paths if str(item).strip()]
        if not normalized:
            return 0

        try:
            file_inputs = page.query_selector_all("input[type='file']")
        except Exception as exc:
            raise ValueError(f"failed to query file inputs: {exc}")

        if not file_inputs:
            raise ValueError("publish page has no file input")

        last_error = None
        for file_input in file_inputs:
            try:
                file_input.set_input_files(normalized)
                return len(normalized)
            except Exception as exc:
                last_error = exc
                continue
        if last_error is not None:
            raise last_error
        return 0

    # ── find_publish_button ─────────────────────────────────────────────────

    def cmd_find_publish_button(self, args: dict) -> dict:
        """Thread-safe: enqueues to worker thread."""
        return self._enqueue_request("find_publish_button", args)

    def _cmd_find_publish_button(self, args: dict) -> dict:
        session_id = args["session_id"]
        session = self._resolve_session(session_id)
        page = session.page

        selectors_to_try = [
            "button[type='submit']",
            "button:has-text('发布')",
            "[role='button']:has-text('发布')",
            "button.primary",
            ".publish-btn",
            "[aria-label*='发布']",
        ]
        for selector in selectors_to_try:
            try:
                el = page.query_selector(selector)
                if el and el.is_visible():
                    return {
                        "session_id": session_id,
                        "selector": selector,
                        "found": True,
                    }
            except Exception:
                pass
        return {
            "session_id": session_id,
            "selector": None,
            "found": False,
        }

    def run(self) -> None:
        self._worker_thread = threading.Thread(target=self._run_worker, daemon=True)
        self._worker_thread.start()

        if os.path.exists(self.socket_path):
            os.unlink(self.socket_path)
        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(self.socket_path)
        os.chmod(self.socket_path, 0o600)
        server.listen(16)

        def serve():
            while self._running:
                try:
                    server.settimeout(1.0)
                    try:
                        conn, _ = server.accept()
                    except socket.timeout:
                        continue
                    threading.Thread(target=self._handle_conn, args=(conn,), daemon=True).start()
                except Exception:
                    break

        self._socket_thread = threading.Thread(target=serve, daemon=True)
        self._socket_thread.start()
        self._socket_thread.join()

    def _handle_conn(self, conn) -> None:
        try:
            data = b""
            while True:
                chunk = conn.recv(4096)
                if not chunk:
                    break
                data += chunk
                if b"\n" in data:
                    break
            if not data:
                return
            request = json.loads(data.decode("utf-8"))
            action = request.get("action")
            args = request.get("args", {})
            try:
                if action == "open":
                    result = self.cmd_open(args)
                elif action == "snapshot":
                    result = self.cmd_snapshot(args)
                elif action == "extract":
                    result = self.cmd_extract(args)
                elif action == "close":
                    result = self.cmd_close(args)
                elif action == "fill_form":
                    result = self.cmd_fill_form(args)
                elif action == "click_element":
                    result = self.cmd_click_element(args)
                elif action == "publish":
                    result = self.cmd_publish(args)
                elif action == "find_publish_button":
                    result = self.cmd_find_publish_button(args)
                elif action == "evaluate":
                    result = self.cmd_evaluate(args)
                elif action == "ping":
                    result = {"ok": True, "result": {"status": "ok", "socket_path": self.socket_path}}
                elif action == "shutdown":
                    result = self.cmd_shutdown(args)
                else:
                    result = {"ok": False, "error": f"unknown action: {action}"}
            except Exception as exc:
                result = {"ok": False, "error": str(exc)}
            conn.sendall((json.dumps(result) + "\n").encode("utf-8"))
        except Exception:
            pass
        finally:
            conn.close()


def run_daemon(socket_path: str) -> None:
    daemon = DriverDaemon(socket_path)
    daemon.run()


def send_to_daemon(socket_path: str, action: str, args: dict) -> dict:
    request = {"action": action, "args": args}
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.settimeout(30)
    try:
        sock.connect(socket_path)
        sock.sendall((json.dumps(request) + "\n").encode("utf-8"))
        response_bytes = b""
        while True:
            chunk = sock.recv(4096)
            if not chunk:
                break
            response_bytes += chunk
            if b"\n" in response_bytes:
                break
        try:
            response = json.loads(response_bytes.decode("utf-8"))
        except Exception as exc:
            raise Exception(f"daemon returned invalid JSON: {exc} raw={response_bytes[:200]!r}")
        if not isinstance(response, dict):
            raise Exception(f"daemon returned non-dict response: {type(response).__name__} {str(response)[:200]}")
        if not response.get("ok"):
            raise Exception(response.get("error", "unknown error"))
        return response.get("result", {}) if isinstance(response.get("result"), dict) else {}
    finally:
        sock.close()


def daemon_is_responsive(socket_path: str) -> bool:
    if not os.path.exists(socket_path):
        return False
    try:
        send_to_daemon(socket_path, "ping", {})
        return True
    except Exception:
        return False


def daemon_pid(socket_path: str) -> int | None:
    pidfile = socket_path + ".pid"
    if not os.path.exists(pidfile):
        return None
    try:
        with open(pidfile) as f:
            return int(f.read().strip())
    except Exception:
        return None


def _is_process_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def ensure_daemon(socket_path: str) -> None:
    if daemon_is_responsive(socket_path):
        return

    pid = daemon_pid(socket_path)
    if pid and _is_process_alive(pid) and daemon_is_responsive(socket_path):
        return

    lock_fd = _acquire_startup_lock(socket_path)
    if lock_fd is None:
        return
    try:
        if daemon_is_responsive(socket_path):
            return

        pid = daemon_pid(socket_path)
        if pid and _is_process_alive(pid) and daemon_is_responsive(socket_path):
            return

        _cleanup_stale_daemon_artifacts(socket_path)
        _terminate_duplicate_daemons(socket_path)

        script_path = os.path.abspath(__file__)
        devnull = open(os.devnull, "w")
        proc = subprocess.Popen(
            [sys.executable, script_path, "daemon", socket_path],
            stdout=devnull,
            stderr=devnull,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
        )
        with open(socket_path + ".pid", "w") as f:
            f.write(str(proc.pid))
        for _ in range(50):
            if daemon_is_responsive(socket_path):
                return
            time.sleep(0.1)
        raise RuntimeError(f"browser driver daemon did not become responsive: {socket_path}")
    finally:
        os.close(lock_fd)
        try:
            os.unlink(socket_path + ".lock")
        except Exception:
            pass


def _acquire_startup_lock(socket_path: str) -> int | None:
    lockfile = socket_path + ".lock"
    deadline = time.monotonic() + 5.0
    while True:
        try:
            return os.open(lockfile, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            if daemon_is_responsive(socket_path):
                return None
            if time.monotonic() >= deadline:
                try:
                    os.unlink(lockfile)
                except FileNotFoundError:
                    pass
                except Exception:
                    pass
            time.sleep(0.1)


def _cleanup_stale_daemon_artifacts(socket_path: str) -> None:
    for path in (socket_path, socket_path + ".pid"):
        try:
            os.unlink(path)
        except FileNotFoundError:
            pass
        except Exception:
            pass


def _terminate_duplicate_daemons(socket_path: str) -> None:
    script_name = os.path.basename(__file__)
    escaped_socket = re.escape(socket_path)
    pattern = re.compile(rf"^\s*(\d+)\s+.*{re.escape(script_name)}\s+daemon\s+{escaped_socket}\s*$")
    try:
        completed = subprocess.run(
            ["ps", "-axo", "pid=,command="],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
    except Exception:
        return

    current_pid = os.getpid()
    for line in completed.stdout.splitlines():
        match = pattern.match(line.strip())
        if not match:
            continue
        pid = int(match.group(1))
        if pid == current_pid:
            continue
        try:
            os.kill(pid, 15)
        except Exception:
            continue


def main() -> None:
    if len(sys.argv) < 2:
        print(json.dumps({"error": "usage: driver.py <action> <args_json>"}), file=sys.stderr)
        sys.exit(1)

    mode = sys.argv[1]

    if mode == "daemon":
        if len(sys.argv) < 3:
            print(json.dumps({"error": "usage: driver.py daemon <socket_path>"}), file=sys.stderr)
            sys.exit(1)
        run_daemon(sys.argv[2])
        return

    if len(sys.argv) < 3:
        print(json.dumps({"error": "usage: driver.py <action> <args_json>"}), file=sys.stderr)
        sys.exit(1)

    action = mode
    try:
        args = json.loads(sys.argv[2])
    except json.JSONDecodeError as exc:
        print(json.dumps({"error": f"invalid JSON args: {exc}"}), file=sys.stderr)
        sys.exit(1)

    socket_path = os.getenv("BROWSER_DRIVER_SOCKET") or os.path.join(
        os.getenv("TMPDIR") or "/tmp", "browser_driver.sock"
    )

    ensure_daemon(socket_path)

    try:
        result = send_to_daemon(socket_path, action, args)
    except Exception as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        sys.exit(1)

    print(json.dumps(result))


if __name__ == "__main__":
    main()
