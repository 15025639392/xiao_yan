from app.usecases import xiaohongshu_publish_autofill as publish_autofill


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
