from app.usecases import xiaohongshu_publish_autofill as publish_autofill
from app.usecases import xiaohongshu_text_image_autofill as text_image_autofill


def test_autofill_publish_page_returns_filled_when_browser_organ_works(monkeypatch):
    def mock_call_browser_capability(capability, args, *, timeout_seconds=15.0):
        if capability == "browser.open":
            return {"session_id": "test-session-123", "url": args["url"], "status": "active"}
        if capability == "browser.publish":
            return {"status": "filled", "filled_title": True, "filled_body": True, "publish_clicked": False}
        if capability == "browser.close":
            return {"session_id": args["session_id"], "status": "closed"}
        return {}

    monkeypatch.setattr(publish_autofill, "call_browser_capability", mock_call_browser_capability)

    result = publish_autofill.autofill_xiaohongshu_publish_page(title="测试标题", body="测试正文")

    assert result.status == "filled"
    assert result.filled_title is True
    assert result.filled_body is True
    assert "标题和正文草稿填进" in result.message


def test_autofill_publish_page_returns_browser_unavailable_when_organ_missing(monkeypatch):
    def mock_call_browser_capability(capability, args, *, timeout_seconds=15.0):
        from app.api.tool_capability_bridge import BrowserOrganUnavailable
        raise BrowserOrganUnavailable("browser organ unavailable")

    monkeypatch.setattr(publish_autofill, "call_browser_capability", mock_call_browser_capability)

    result = publish_autofill.autofill_xiaohongshu_publish_page(title="测试标题", body="测试正文")

    assert result.status == "browser_unavailable"
    assert result.filled_title is False
    assert "浏览器器官不可用" in result.message


def test_autofill_publish_page_returns_open_failed_when_no_session(monkeypatch):
    def mock_call_browser_capability(capability, args, *, timeout_seconds=15.0):
        if capability == "browser.open":
            return {"session_id": None, "url": args["url"], "status": "failed"}
        return {}

    monkeypatch.setattr(publish_autofill, "call_browser_capability", mock_call_browser_capability)

    result = publish_autofill.autofill_xiaohongshu_publish_page(title="测试标题", body="测试正文")

    assert result.status == "open_failed"
    assert "打开发布页失败" in result.message


def test_autofill_publish_page_returns_awaiting_image_upload_when_form_not_ready(monkeypatch):
    def mock_call_browser_capability(capability, args, *, timeout_seconds=15.0):
        if capability == "browser.open":
            return {"session_id": "test-session-123", "url": args["url"], "status": "active"}
        if capability == "browser.publish":
            return {"status": "awaiting_image_upload", "filled_title": False, "filled_body": False, "publish_clicked": False}
        if capability == "browser.close":
            return {"session_id": args["session_id"], "status": "closed"}
        return {}

    monkeypatch.setattr(publish_autofill, "call_browser_capability", mock_call_browser_capability)

    result = publish_autofill.autofill_xiaohongshu_publish_page(title="测试标题", body="测试正文")

    assert result.status == "awaiting_image_upload"
    assert result.filled_title is False
    assert "上传首图" in result.message


def test_autofill_publish_page_closes_session_on_publish_error(monkeypatch):
    close_sessions = []

    def mock_call_browser_capability(capability, args, *, timeout_seconds=15.0):
        if capability == "browser.open":
            return {"session_id": "test-session-123", "url": args["url"], "status": "active"}
        if capability == "browser.close":
            close_sessions.append(args["session_id"])
            return {"session_id": args["session_id"], "status": "closed"}
        if capability == "browser.publish":
            from app.api.tool_capability_bridge import BrowserCapabilityError
            raise BrowserCapabilityError("publish failed", "req-123")
        return {}

    monkeypatch.setattr(publish_autofill, "call_browser_capability", mock_call_browser_capability)

    result = publish_autofill.autofill_xiaohongshu_publish_page(title="测试标题", body="测试正文")

    assert result.status == "publish_failed"
    assert "test-session-123" in close_sessions
    assert "发布失败" in result.message


def test_autofill_auto_publish_clicks_publish_button(monkeypatch):
    clicked_sessions = []

    def mock_call_browser_capability(capability, args, *, timeout_seconds=15.0):
        if capability == "browser.open":
            return {"session_id": "test-session-123", "url": args["url"], "status": "active"}
        if capability == "browser.close":
            return {"session_id": args["session_id"], "status": "closed"}
        if capability == "browser.publish":
            clicked_sessions.append(args.get("publish_selector"))
            return {"status": "filled", "filled_title": True, "filled_body": True, "publish_clicked": True}

    monkeypatch.setattr(publish_autofill, "call_browser_capability", mock_call_browser_capability)

    result = publish_autofill.autofill_xiaohongshu_publish_page(
        title="测试标题", body="测试正文", auto_publish=True, publish_selector="button[type='submit']"
    )

    assert result.status == "filled"
    assert "button[type='submit']" in clicked_sessions
    assert "自动打开发布页、填入草稿并点击发布按钮" in result.message


def test_autofill_auto_publish_requires_selector(monkeypatch):
    def mock_call_browser_capability(capability, args, *, timeout_seconds=15.0):
        return {}

    monkeypatch.setattr(publish_autofill, "call_browser_capability", mock_call_browser_capability)

    result = publish_autofill.autofill_xiaohongshu_publish_page(
        title="测试标题", body="测试正文", auto_publish=True, publish_selector=""
    )

    assert result.status == "missing_selector"
    assert "auto_publish requires publish_selector" in result.message


def test_autofill_requires_non_blank_title():
    try:
        publish_autofill.autofill_xiaohongshu_publish_page(title="  ", body="测试正文")
    except ValueError as exc:
        assert str(exc) == "publish title cannot be blank"
    else:
        raise AssertionError("expected ValueError for blank title")


def test_autofill_requires_non_blank_body():
    try:
        publish_autofill.autofill_xiaohongshu_publish_page(title="测试标题", body="  ")
    except ValueError as exc:
        assert str(exc) == "publish body cannot be blank"
    else:
        raise AssertionError("expected ValueError for blank body")


# ── text_image_autofill tests (browser organ only) ────────────────────────────


def test_text_image_autofill_submits_generation_when_editors_are_ready(monkeypatch):
    def mock_call_browser_capability(capability, args, *, timeout_seconds=15.0):
        _ = timeout_seconds
        if capability == "browser.open":
            return {"session_id": "text-image-session", "url": args["url"], "status": "active"}
        if capability == "browser.evaluate":
            return {
                "session_id": args["session_id"],
                "result": '{"status":"submitted_generation","filled_cards":3,"clicked_generate":true}',
            }
        if capability == "browser.close":
            return {"session_id": args["session_id"], "status": "closed"}
        return {}

    monkeypatch.setattr(text_image_autofill, "call_browser_capability", mock_call_browser_capability)

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
    def mock_call_browser_capability(capability, args, *, timeout_seconds=15.0):
        _ = timeout_seconds
        if capability == "browser.open":
            return {"session_id": "text-image-session", "url": args["url"], "status": "active"}
        if capability == "browser.evaluate":
            return {
                "session_id": args["session_id"],
                "result": '{"status":"partial_cards","filled_cards":1,"clicked_generate":false}',
            }
        if capability == "browser.close":
            return {"session_id": args["session_id"], "status": "closed"}
        return {}

    monkeypatch.setattr(text_image_autofill, "call_browser_capability", mock_call_browser_capability)

    result = text_image_autofill.autofill_xiaohongshu_text_image_cards(
        cards=["封面标题", "步骤拆解", "评论引导"],
        trigger_generate=False,
    )

    assert result.status == "needs_manual_expand"
    assert result.filled_cards == 1
    assert "再写一张" in result.message


def test_text_image_autofill_returns_browser_unavailable_when_organ_missing(monkeypatch):
    def mock_call_browser_capability(capability, args, *, timeout_seconds=15.0):
        _ = (capability, args, timeout_seconds)
        from app.api.tool_capability_bridge import BrowserOrganUnavailable

        raise BrowserOrganUnavailable("browser organ unavailable")

    monkeypatch.setattr(text_image_autofill, "call_browser_capability", mock_call_browser_capability)

    result = text_image_autofill.autofill_xiaohongshu_text_image_cards(
        cards=["封面标题", "步骤拆解"],
        trigger_generate=False,
    )

    assert result.status == "browser_unavailable"
    assert "浏览器器官不可用" in result.message
