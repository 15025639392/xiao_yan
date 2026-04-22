from __future__ import annotations

import base64
from pathlib import Path

from app.api.platform_route_models import XiaohongshuCoverPreviewResponse
from app.usecases.xiaohongshu_cover_image import (
    XiaohongshuCoverImageGenerationError,
    XiaohongshuCoverImageUnavailableError,
    generate_xiaohongshu_cover_image,
)
from app.usecases.xiaohongshu_cover_templates import list_xiaohongshu_cover_templates


def preview_xiaohongshu_cover_image(
    *,
    title: str,
    body: str,
    template_name: str | None = None,
) -> XiaohongshuCoverPreviewResponse:
    normalized_title = title.strip()
    normalized_body = body.strip()
    if not normalized_title:
        raise ValueError("cover preview title cannot be blank")
    if not normalized_body:
        raise ValueError("cover preview body cannot be blank")

    try:
        result = generate_xiaohongshu_cover_image(
            title=normalized_title,
            body=normalized_body,
            template_name=template_name,
        )
    except (XiaohongshuCoverImageUnavailableError, XiaohongshuCoverImageGenerationError) as exc:
        raise ValueError(str(exc)) from exc

    image_bytes = Path(result.path).read_bytes()
    image_data_url = f"data:image/png;base64,{base64.b64encode(image_bytes).decode('ascii')}"
    return XiaohongshuCoverPreviewResponse(
        title=normalized_title,
        body=normalized_body,
        template_name=result.template_name,
        available_templates=list_xiaohongshu_cover_templates(),
        image_path=result.path,
        image_data_url=image_data_url,
    )
