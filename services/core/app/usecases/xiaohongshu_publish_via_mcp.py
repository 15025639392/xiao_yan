from __future__ import annotations

from pathlib import Path

from app.api.platform_route_models import XiaohongshuPublishViaMcpResponse
from app.external_executors.xiaohongshu_mcp_client import (
    XiaohongshuMcpClient,
    XiaohongshuMcpClientDisabledError,
    XiaohongshuMcpClientUnavailableError,
)


def publish_xiaohongshu_image_post_via_mcp(
    *,
    title: str,
    body: str,
    image_paths: list[str],
    client: XiaohongshuMcpClient,
) -> XiaohongshuPublishViaMcpResponse:
    normalized_title = title.strip()
    normalized_body = body.strip()
    normalized_image_paths = _normalize_image_paths(image_paths)

    if not normalized_title:
        raise ValueError("publish title cannot be blank")
    if not normalized_body:
        raise ValueError("publish body cannot be blank")
    if not normalized_image_paths:
        raise ValueError("image paths cannot be empty")

    try:
        result = client.publish_image_post(
            title=normalized_title,
            content=normalized_body,
            images=normalized_image_paths,
        )
    except XiaohongshuMcpClientDisabledError:
        return XiaohongshuPublishViaMcpResponse(
            status="publisher_disabled",
            message="MCP 发布失败：当前未启用 xiaohongshu-mcp 发布器。",
            published_title=normalized_title,
            image_count=len(normalized_image_paths),
            image_paths=normalized_image_paths,
        )
    except XiaohongshuMcpClientUnavailableError as exc:
        return XiaohongshuPublishViaMcpResponse(
            status="service_unreachable",
            message=f"MCP 发布失败：服务不可达。{exc}",
            published_title=normalized_title,
            image_count=len(normalized_image_paths),
            image_paths=normalized_image_paths,
        )

    return XiaohongshuPublishViaMcpResponse(
        status=result.status,
        message=f"MCP 发布结果：{result.message}",
        published_title=normalized_title,
        image_count=len(normalized_image_paths),
        image_paths=normalized_image_paths,
        post_url=result.post_url,
        platform_post_id=result.platform_post_id,
    )


def _normalize_image_paths(image_paths: list[str]) -> list[str]:
    normalized: list[str] = []
    for raw in image_paths:
        candidate = raw.strip()
        if not candidate:
            continue
        path = Path(candidate).expanduser()
        if not path.is_absolute():
            raise ValueError(f"image path must be absolute: {candidate}")
        if not path.exists():
            raise ValueError(f"image path does not exist: {candidate}")
        if not path.is_file():
            raise ValueError(f"image path is not a file: {candidate}")
        normalized.append(str(path))
    return normalized
