from __future__ import annotations

from app.api.platform_handlers_core import _wrap_platform_errors
from app.platform_adapters.service import PlatformAdapterService
from app.usecases.xiaohongshu_cover_preview import preview_xiaohongshu_cover_image


def handle_xiaohongshu_cover_preview(
    *,
    title: str,
    body: str,
    template_name: str | None,
    service: PlatformAdapterService,
):
    return _wrap_platform_errors(
        service,
        lambda: preview_xiaohongshu_cover_image(
            title=title,
            body=body,
            template_name=template_name,
        ),
    )
