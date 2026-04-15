from __future__ import annotations

import json
import select
import subprocess
import time
from typing import Any


class StdioMcpClient:
    def __init__(
        self,
        *,
        command: str,
        args: list[str] | None = None,
        cwd: str | None = None,
        env: dict[str, str] | None = None,
        timeout_seconds: int = 20,
    ) -> None:
        self._timeout_seconds = max(1, min(120, int(timeout_seconds)))
        self._next_id = 1
        self._process = subprocess.Popen(
            [command, *(args or [])],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=cwd,
            env=env or None,
        )

        if self._process.stdin is None or self._process.stdout is None:
            raise RuntimeError("failed to open MCP stdio pipes")

    def close(self) -> None:
        if self._process.poll() is not None:
            return
        try:
            self._process.terminate()
            self._process.wait(timeout=1)
        except Exception:  # noqa: BLE001
            try:
                self._process.kill()
            except Exception:  # noqa: BLE001
                pass

    def initialize(self) -> None:
        _ = self.request(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "clientInfo": {"name": "digital-being-core", "version": "0.1.0"},
                "capabilities": {},
            },
        )
        self.notify("notifications/initialized", {})

    def list_tools(self) -> list[dict[str, Any]]:
        result = self.request("tools/list", {})
        tools = result.get("tools")
        if not isinstance(tools, list):
            return []
        normalized: list[dict[str, Any]] = []
        for item in tools:
            if not isinstance(item, dict):
                continue
            name = item.get("name")
            if not isinstance(name, str) or not name.strip():
                continue
            normalized.append(item)
        return normalized

    def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        result = self.request(
            "tools/call",
            {
                "name": tool_name,
                "arguments": arguments,
            },
        )
        if not isinstance(result, dict):
            return {"result": result}
        return result

    def notify(self, method: str, params: dict[str, Any]) -> None:
        self._write_message(
            {
                "jsonrpc": "2.0",
                "method": method,
                "params": params,
            }
        )

    def request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        if self._process.poll() is not None:
            stderr = self._safe_read_stderr()
            raise RuntimeError(f"mcp process already exited: {stderr or 'unknown error'}")

        request_id = self._next_id
        self._next_id += 1
        self._write_message(
            {
                "jsonrpc": "2.0",
                "id": request_id,
                "method": method,
                "params": params,
            }
        )

        deadline = time.monotonic() + self._timeout_seconds
        while time.monotonic() < deadline:
            remaining = max(0.0, deadline - time.monotonic())
            payload = self._read_message_with_timeout(remaining)
            if payload is None:
                continue
            if payload.get("id") != request_id:
                continue
            if "error" in payload:
                error = payload.get("error")
                if isinstance(error, dict):
                    message = error.get("message")
                    if isinstance(message, str) and message.strip():
                        raise RuntimeError(message)
                raise RuntimeError(f"mcp request failed for method={method}")
            result = payload.get("result")
            if isinstance(result, dict):
                return result
            return {"result": result}

        raise RuntimeError(f"mcp request timed out for method={method}")

    def _write_message(self, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        header = f"Content-Length: {len(body)}\r\n\r\n".encode("ascii")
        assert self._process.stdin is not None
        self._process.stdin.write(header)
        self._process.stdin.write(body)
        self._process.stdin.flush()

    def _read_message_with_timeout(self, timeout_seconds: float) -> dict[str, Any] | None:
        if timeout_seconds <= 0:
            return None
        assert self._process.stdout is not None
        fd = self._process.stdout.fileno()
        ready, _, _ = select.select([fd], [], [], timeout_seconds)
        if not ready:
            return None
        return self._read_message()

    def _read_message(self) -> dict[str, Any]:
        assert self._process.stdout is not None

        content_length: int | None = None
        while True:
            line = self._process.stdout.readline()
            if line == b"":
                stderr = self._safe_read_stderr()
                raise RuntimeError(f"mcp process closed stdout unexpectedly: {stderr or 'no stderr'}")
            if line in {b"\r\n", b"\n"}:
                break
            decoded = line.decode("utf-8", errors="replace").strip()
            if not decoded:
                break
            if ":" not in decoded:
                continue
            key, value = decoded.split(":", 1)
            if key.strip().lower() == "content-length":
                try:
                    content_length = int(value.strip())
                except ValueError as exc:
                    raise RuntimeError("invalid MCP content-length header") from exc

        if content_length is None or content_length < 0:
            raise RuntimeError("missing MCP content-length header")

        body = self._process.stdout.read(content_length)
        if body is None or len(body) != content_length:
            raise RuntimeError("failed to read full MCP response body")

        try:
            payload = json.loads(body.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise RuntimeError("invalid MCP JSON payload") from exc

        if not isinstance(payload, dict):
            raise RuntimeError("invalid MCP payload type")
        return payload

    def _safe_read_stderr(self) -> str:
        try:
            assert self._process.stderr is not None
            raw = self._process.stderr.read()
            if isinstance(raw, bytes):
                return raw.decode("utf-8", errors="replace").strip()
            return str(raw).strip()
        except Exception:  # noqa: BLE001
            return ""
