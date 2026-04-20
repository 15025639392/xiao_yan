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
import socket
import subprocess
import sys
import threading
import queue
from datetime import datetime, timezone
from typing import Any


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
                    else:
                        error = f"unknown action: {action}"
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
                session.browser.close()
            except Exception:
                pass
        self.sessions.clear()
        return {"ok": True}

    # --- Commands run on worker thread (no GIL issues) ---

    def _cmd_open(self, args: dict, pw) -> dict:
        from playwright.sync_api import Error as PlaywrightError

        url = args["url"]
        session_id = args.get("session_id") or f"browser-{os.urandom(8).hex()}"
        headless = args.get("headless", True)
        wait_until = args.get("wait_until", "domcontentloaded")

        browser = pw.chromium.launch(headless=headless)
        context = browser.new_context()
        page = context.new_page()

        nav_err: str | None = None
        try:
            page.goto(url, wait_until=wait_until, timeout=15000)
        except PlaywrightError as exc:
            nav_err = str(exc)

        if nav_err is None:
            self.sessions[session_id] = BrowserSession(session_id, browser, context, page)
        else:
            browser.close()
            raise RuntimeError(f"navigation failed: {nav_err}")

        resolved_url = page.url
        title = page.title()

        self.sessions[session_id] = BrowserSession(session_id, browser, context, page)

        return {
            "session_id": session_id,
            "url": url,
            "resolved_url": resolved_url,
            "title": title,
            "status": "active",
            "opened_at": now_iso(),
        }

    def _cmd_snapshot(self, args: dict) -> dict:
        session_id = args["session_id"]
        include_text = args.get("include_text", True)
        include_accessibility = args.get("include_accessibility", False)
        include_screenshot = args.get("include_screenshot", False)
        max_text_bytes = args.get("max_text_bytes", 512 * 1024)

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
                session.browser.close()
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
        if session.context.browser.is_connected() is False:
            raise ValueError(f"session browser disconnected: {session_id}")
        return session

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
        response = json.loads(response_bytes.decode("utf-8"))
        if not response.get("ok"):
            raise Exception(response.get("error", "unknown error"))
        return response.get("result", {})
    finally:
        sock.close()


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
    pid = daemon_pid(socket_path)
    if pid and _is_process_alive(pid):
        return

    lockfile = socket_path + ".lock"
    lock_fd = os.open(lockfile, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        pid = daemon_pid(socket_path)
        if pid and _is_process_alive(pid):
            return

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
        import time
        for _ in range(50):
            if os.path.exists(socket_path):
                time.sleep(0.1)
                break
            time.sleep(0.1)
    finally:
        os.close(lock_fd)
        try:
            os.unlink(lockfile)
        except Exception:
            pass


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
