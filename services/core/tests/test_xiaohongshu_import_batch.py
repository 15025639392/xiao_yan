import json
from pathlib import Path

import pytest

from app.api.platform_route_models import XiaohongshuImportFilePreviewRequest
from app.usecases.xiaohongshu_import_batch import load_xiaohongshu_import_batch


def test_load_xiaohongshu_import_batch_from_list_payload(tmp_path: Path):
    payload_path = tmp_path / "xhs_batch.json"
    payload_path.write_text(
        json.dumps(
            [
                {
                    "item_type": "comment",
                    "comment": {
                        "comment_id": "comment_1",
                        "note_id": "note_1",
                        "comment_text": "适合新手吗？",
                        "author": {"id": "author_1", "name": "青栀"},
                    },
                },
                {
                    "item_type": "note",
                    "note": {
                        "note_id": "note_2",
                        "note_text": "今天想讲怎么收窄复杂度。",
                        "author": {"id": "author_2", "name": "晚晴"},
                    },
                },
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    items = load_xiaohongshu_import_batch(
        XiaohongshuImportFilePreviewRequest(path=str(payload_path))
    )

    assert len(items) == 2
    assert items[0].item_type == "comment"
    assert items[1].item_type == "note"


def test_load_xiaohongshu_import_batch_rejects_missing_file():
    with pytest.raises(ValueError, match="file not found"):
        load_xiaohongshu_import_batch(
            XiaohongshuImportFilePreviewRequest(path="/tmp/does-not-exist-xhs.json")
        )


def test_load_xiaohongshu_import_batch_rejects_invalid_shape(tmp_path: Path):
    payload_path = tmp_path / "xhs_invalid.json"
    payload_path.write_text(json.dumps({"foo": "bar"}), encoding="utf-8")

    with pytest.raises(ValueError, match="must contain a JSON list"):
        load_xiaohongshu_import_batch(
            XiaohongshuImportFilePreviewRequest(path=str(payload_path))
        )
