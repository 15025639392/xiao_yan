from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class XiaohongshuBrowserReviewPreparation:
    ready: bool
    focus: str = ""
    next_action: str = ""
    blocking_reason: str = ""


def evaluate_xiaohongshu_browser_review_preparation(
    *,
    publish_result: dict,
    requested_image_paths: list[str],
) -> XiaohongshuBrowserReviewPreparation:
    requested_count = len([item for item in requested_image_paths if str(item).strip()])
    filled_title = bool(publish_result.get("filled_title", False))
    filled_body = bool(publish_result.get("filled_body", False))
    status = str(publish_result.get("status", "unknown"))
    upload_error = str(publish_result.get("upload_error", "") or "").strip()

    raw_uploaded_count = publish_result.get("uploaded_image_count", 0)
    uploaded_image_count = raw_uploaded_count if isinstance(raw_uploaded_count, int) else 0

    if upload_error and requested_count > 0:
        return XiaohongshuBrowserReviewPreparation(
            ready=False,
            blocking_reason=f"自动上传封面失败：{upload_error}",
        )

    if requested_count > 0 and uploaded_image_count <= 0:
        return XiaohongshuBrowserReviewPreparation(
            ready=False,
            blocking_reason="封面图还没成功上传到发布页",
        )

    if filled_title and filled_body:
        return XiaohongshuBrowserReviewPreparation(
            ready=True,
            focus="已上传并填好，停在发布前最后一步",
            next_action="请检查封面、标题和正文，确认无误后再点击发布。",
        )

    if status == "awaiting_image_upload":
        return XiaohongshuBrowserReviewPreparation(
            ready=False,
            blocking_reason="发布页还停在首图上传前置步骤",
        )

    if filled_title or filled_body:
        return XiaohongshuBrowserReviewPreparation(
            ready=False,
            blocking_reason="标题和正文还没有完整填入发布页",
        )

    return XiaohongshuBrowserReviewPreparation(
        ready=False,
        blocking_reason="当前页面还没识别到可填写的标题和正文输入区",
    )
