from __future__ import annotations

from pathlib import Path
from typing import Any

from app.api.platform_route_models import (
    XiaohongshuImportBatchItem,
    XiaohongshuImportFilePreviewRequest,
    XiaohongshuImportPreviewRequest,
)
from app.utils.file_utils import read_json_file


def load_xiaohongshu_import_batch(
    request_body: XiaohongshuImportFilePreviewRequest,
) -> list[XiaohongshuImportBatchItem]:
    file_path = Path(request_body.path).expanduser()
    if not file_path.exists():
        raise ValueError("xiaohongshu import file not found")
    if not file_path.is_file():
        raise ValueError("xiaohongshu import path is not a file")

    payload = read_json_file(file_path)
    raw_items = _normalize_batch_payload(payload)
    items: list[XiaohongshuImportBatchItem] = []
    for index, raw_item in enumerate(raw_items):
        if not isinstance(raw_item, dict):
            raise ValueError("xiaohongshu import items must be objects")
        item_request = XiaohongshuImportPreviewRequest.model_validate(raw_item)
        items.append(
            XiaohongshuImportBatchItem(
                index=index,
                item_type=item_request.item_type,
                request=item_request,
            )
        )
    return items


def _normalize_batch_payload(payload: Any) -> list[Any]:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        items = payload.get("items")
        if isinstance(items, list):
            return items
    raise ValueError("xiaohongshu import file must contain a JSON list or an {\"items\": [...]} object")
