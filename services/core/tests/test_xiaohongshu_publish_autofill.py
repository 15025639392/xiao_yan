from app.usecases import xiaohongshu_publish_autofill as publish_autofill
from app.usecases import xiaohongshu_text_image_autofill as text_image_autofill


def test_autofill_publish_page_returns_awaiting_image_upload_when_form_not_ready(monkeypatch):
    monkeypatch.setattr(publish_autofill, "_open_chrome_publish_page", lambda: None)
    monkeypatch.setattr(
        publish_autofill,
        "_execute_active_tab_javascript",
        lambda script: '{"status":"awaiting_image_upload","filled_title":false,"filled_body":false}',
    )

    result = publish_autofill.autofill_xiaohongshu_publish_page(title="测试标题", body="测试正文")

    assert result.status == "awaiting_image_upload"
    assert result.filled_title is False
    assert "上传首图" in result.message


def test_autofill_publish_page_returns_opened_only_when_chrome_js_is_disabled(monkeypatch):
    monkeypatch.setattr(publish_autofill, "_open_chrome_publish_page", lambda: None)

    def raise_js_disabled(script: str) -> str:
        _ = script
        raise ValueError("execution error: 通过 AppleScript 执行 JavaScript 的功能已关闭。")

    monkeypatch.setattr(publish_autofill, "_execute_active_tab_javascript", raise_js_disabled)

    result = publish_autofill.autofill_xiaohongshu_publish_page(title="测试标题", body="测试正文")

    assert result.status == "opened_publish_page"
    assert result.filled_title is False
    assert "手动粘贴" in result.message


def test_text_image_autofill_submits_generation_when_editors_are_ready(monkeypatch):
    monkeypatch.setattr(text_image_autofill, "_open_chrome_publish_page", lambda: None)
    monkeypatch.setattr(
        text_image_autofill,
        "_execute_active_tab_javascript",
        lambda script: '{"status":"submitted_generation","filled_cards":3,"clicked_generate":true}',
    )

    result = text_image_autofill.autofill_xiaohongshu_text_image_cards(
        cards=["封面标题", "步骤拆解", "评论引导"],
        trigger_generate=True,
    )

    assert result.status == "submitted_generation"
    assert result.filled_cards == 3
    assert result.clicked_generate is True
    assert "触发了生成图片" in result.message


def test_text_image_autofill_requires_non_blank_cards():
    try:
        text_image_autofill.autofill_xiaohongshu_text_image_cards(cards=["  ", ""], trigger_generate=True)
    except ValueError as exc:
        assert str(exc) == "text image cards cannot be empty"
    else:
        raise AssertionError("expected ValueError for empty text image cards")


def test_text_image_autofill_returns_manual_expand_status_when_only_cover_is_filled(monkeypatch):
    monkeypatch.setattr(text_image_autofill, "_open_chrome_publish_page", lambda: None)
    monkeypatch.setattr(
        text_image_autofill,
        "_execute_active_tab_javascript",
        lambda script: '{"status":"partial_cards","filled_cards":1,"clicked_generate":false}',
    )

    result = text_image_autofill.autofill_xiaohongshu_text_image_cards(
        cards=["封面标题", "步骤拆解", "评论引导"],
        trigger_generate=False,
    )

    assert result.status == "needs_manual_expand"
    assert result.filled_cards == 1
    assert "点一次“再写一张”" in result.message
