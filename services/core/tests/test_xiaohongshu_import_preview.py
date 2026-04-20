import pytest

from app.api.platform_route_models import (
    XiaohongshuAuthorSnapshot,
    XiaohongshuCommentSnapshot,
    XiaohongshuImportPreviewRequest,
    XiaohongshuNoteSnapshot,
)
from app.usecases.xiaohongshu_import_preview import build_xiaohongshu_import_envelope


def test_build_xiaohongshu_comment_import_envelope():
    envelope = build_xiaohongshu_import_envelope(
        XiaohongshuImportPreviewRequest(
            item_type="comment",
            comment=XiaohongshuCommentSnapshot(
                comment_id="comment_1",
                note_id="note_1",
                comment_text="学生党适合这样开始吗？",
                note_title="把复杂系统收成一条主线",
                note_text="先做最小闭环。",
                author=XiaohongshuAuthorSnapshot(id="author_1", name="青栀"),
            ),
        )
    )

    assert envelope.preferred_kind == "comment_reply"
    assert envelope.raw_payload["comment_id"] == "comment_1"
    assert "评论内容：学生党适合这样开始吗？" in (envelope.message or "")


def test_build_xiaohongshu_note_import_envelope():
    envelope = build_xiaohongshu_import_envelope(
        XiaohongshuImportPreviewRequest(
            item_type="note",
            note=XiaohongshuNoteSnapshot(
                note_id="note_2",
                title="先做最小闭环",
                note_text="今天想讲怎么把复杂事情收窄。",
                topic="效率",
                author=XiaohongshuAuthorSnapshot(id="author_2", name="晚晴"),
            ),
        )
    )

    assert envelope.preferred_kind == "note_draft"
    assert envelope.raw_payload["note_id"] == "note_2"
    assert "素材内容：今天想讲怎么把复杂事情收窄。" in (envelope.message or "")


def test_build_xiaohongshu_import_envelope_rejects_missing_required_snapshot():
    with pytest.raises(ValueError, match="comment snapshot is required"):
        build_xiaohongshu_import_envelope(
            XiaohongshuImportPreviewRequest(
                item_type="comment",
            )
        )
