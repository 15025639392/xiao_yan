from __future__ import annotations

from pathlib import Path

from app.api.platform_route_models import XiaohongshuPublishViaMcpResponse
from app.external_executors.xiaohongshu_mcp_client import (
    XiaohongshuMcpClient,
    XiaohongshuMcpClientDisabledError,
    XiaohongshuMcpClientUnavailableError,
)
from app.usecases.xiaohongshu_cover_image import (
    XiaohongshuCoverImageGenerationError,
    XiaohongshuCoverImageUnavailableError,
    generate_xiaohongshu_cover_image,
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

    if not normalized_title:
        raise ValueError("publish title cannot be blank")
    if not normalized_body:
        raise ValueError("publish body cannot be blank")
    if not client.can_publish():
        return XiaohongshuPublishViaMcpResponse(
            status="publisher_disabled",
            message="MCP 发布失败：当前未启用 xiaohongshu-mcp 发布器。",
            published_title=normalized_title,
            image_count=0,
            image_paths=[],
        )

    try:
        normalized_image_paths, generated_cover = _resolve_publish_image_paths(
            title=normalized_title,
            body=normalized_body,
            image_paths=image_paths,
        )
    except XiaohongshuCoverImageUnavailableError:
        return XiaohongshuPublishViaMcpResponse(
            status="cover_generation_unavailable",
            message="MCP 发布前自动生成封面失败：浏览器器官不可用。",
            published_title=normalized_title,
            image_count=0,
            image_paths=[],
        )
    except XiaohongshuCoverImageGenerationError as exc:
        return XiaohongshuPublishViaMcpResponse(
            status="cover_generation_failed",
            message=f"MCP 发布前自动生成封面失败：{exc}",
            published_title=normalized_title,
            image_count=0,
            image_paths=[],
        )

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
        message=_build_publish_message(result.message, generated_cover=generated_cover),
        published_title=normalized_title,
        image_count=len(normalized_image_paths),
        image_paths=normalized_image_paths,
        post_url=result.post_url,
        platform_post_id=result.platform_post_id,
    )


def _resolve_publish_image_paths(*, title: str, body: str, image_paths: list[str]) -> tuple[list[str], bool]:
    normalized_image_paths = _normalize_image_paths(image_paths)
    if normalized_image_paths:
        return normalized_image_paths, False

    generated_cover = generate_xiaohongshu_cover_image(title=title, body=body)
    return [generated_cover.path], True


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


def _build_publish_message(message: str, *, generated_cover: bool) -> str:
    suffix = "；已自动生成封面图。" if generated_cover else ""
    return f"MCP 发布结果：{message}{suffix}"
