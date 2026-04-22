from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx


class XiaohongshuMcpClientError(Exception):
    """Base error for the optional xiaohongshu MCP publisher."""


class XiaohongshuMcpClientDisabledError(XiaohongshuMcpClientError):
    """Raised when the optional publisher is not configured."""


class XiaohongshuMcpClientUnavailableError(XiaohongshuMcpClientError):
    """Raised when the external service cannot be reached."""


class XiaohongshuMcpClientResponseError(XiaohongshuMcpClientError):
    """Raised when the external service returns an unusable payload."""


@dataclass(frozen=True)
class XiaohongshuMcpPublishResult:
    status: str
    message: str
    post_url: str | None = None
    platform_post_id: str | None = None
    raw_response: dict[str, Any] | None = None


class XiaohongshuMcpClient:
    def __init__(
        self,
        *,
        enabled: bool,
        endpoint: str | None,
        timeout_seconds: float = 20.0,
        http_client: httpx.Client | None = None,
    ) -> None:
        self._enabled = enabled
        self._endpoint = (endpoint or "").strip()
        self._timeout_seconds = max(timeout_seconds, 3.0)
        self._http_client = http_client

    def can_publish(self) -> bool:
        return self._enabled and bool(self._endpoint)

    def publish_image_post(self, *, title: str, content: str, images: list[str]) -> XiaohongshuMcpPublishResult:
        if not self.can_publish():
            raise XiaohongshuMcpClientDisabledError("xiaohongshu mcp publisher is disabled")

        payload = {
            "jsonrpc": "2.0",
            "id": "xiao_yan_publish_image_post",
            "method": "tools/call",
            "params": {
                "name": "publish_content",
                "arguments": {
                    "title": title,
                    "content": content,
                    "images": images,
                },
            },
        }

        client = self._http_client or httpx.Client(timeout=httpx.Timeout(self._timeout_seconds, connect=5.0))
        should_close = self._http_client is None
        try:
            response = client.post(self._endpoint, json=payload)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise XiaohongshuMcpClientUnavailableError(f"failed to reach xiaohongshu mcp endpoint: {exc}") from exc
        finally:
            if should_close:
                client.close()

        try:
            body = response.json()
        except ValueError as exc:
            raise XiaohongshuMcpClientResponseError("xiaohongshu mcp returned non-json response") from exc

        return _parse_publish_result(body)


def _parse_publish_result(payload: dict[str, Any]) -> XiaohongshuMcpPublishResult:
    if not isinstance(payload, dict):
        raise XiaohongshuMcpClientResponseError("xiaohongshu mcp returned invalid payload")

    error_payload = payload.get("error")
    if isinstance(error_payload, dict):
        message = str(error_payload.get("message") or "xiaohongshu mcp publish failed")
        return XiaohongshuMcpPublishResult(
            status="publish_failed",
            message=message,
            raw_response=payload,
        )

    result_payload = payload.get("result")
    if not isinstance(result_payload, dict):
        raise XiaohongshuMcpClientResponseError("xiaohongshu mcp result payload is missing")

    structured = result_payload.get("structuredContent")
    if not isinstance(structured, dict):
        structured = {}
    content_entries = result_payload.get("content")
    fallback_text = _extract_text_from_content(content_entries)

    raw_status = structured.get("status")
    status = str(raw_status).strip() if raw_status else "submitted"
    message = str(structured.get("message") or fallback_text or "已提交图文发布")
    post_url = _coerce_optional_string(structured.get("post_url") or structured.get("url"))
    platform_post_id = _coerce_optional_string(structured.get("platform_post_id") or structured.get("post_id"))

    return XiaohongshuMcpPublishResult(
        status=status,
        message=message,
        post_url=post_url,
        platform_post_id=platform_post_id,
        raw_response=payload,
    )


def _extract_text_from_content(content_entries: Any) -> str | None:
    if not isinstance(content_entries, list):
        return None
    parts: list[str] = []
    for item in content_entries:
        if not isinstance(item, dict):
            continue
        text = item.get("text")
        if isinstance(text, str) and text.strip():
            parts.append(text.strip())
    if not parts:
        return None
    return "\n".join(parts)


def _coerce_optional_string(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized or None
