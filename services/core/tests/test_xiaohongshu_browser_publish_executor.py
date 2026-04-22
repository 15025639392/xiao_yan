from app.api.tool_capability_bridge import BrowserCapabilityError, BrowserOrganUnavailable
from app.usecases.xiaohongshu_browser_publish_executor import (
    execute_xiaohongshu_browser_publish,
    resolve_xiaohongshu_publish_selector,
)


def test_resolve_publish_selector_returns_empty_for_manual_review():
    result = resolve_xiaohongshu_publish_selector(
        requires_manual_review=True,
        auto_publish_selector="button[type='submit']",
        find_publish_button=lambda: "button[type='submit']",
        prepare_text_image_cards=lambda: {"status": "submitted_generation"},
    )

    assert result.selector == ""
    assert result.text_image_result is None
    assert result.blocked_reason == ""


def test_resolve_publish_selector_returns_text_image_result_when_button_missing():
    result = resolve_xiaohongshu_publish_selector(
        requires_manual_review=False,
        auto_publish_selector="",
        find_publish_button=lambda: None,
        prepare_text_image_cards=lambda: {"status": "submitted_generation", "message": "ok"},
    )

    assert result.selector == ""
    assert result.text_image_result == {"status": "submitted_generation", "message": "ok"}
    assert result.blocked_reason == ""


def test_execute_browser_publish_returns_blocked_when_open_fails():
    result = execute_xiaohongshu_browser_publish(
        title="标题",
        body="正文",
        selector="",
        image_paths=["/tmp/cover.png"],
        open_publish_page=lambda: (_ for _ in ()).throw(BrowserOrganUnavailable("down")),
        publish_to_page=lambda session_id, title, body, selector, image_paths: {},
    )

    assert result.session_id == ""
    assert result.publish_result is None
    assert result.blocked_reason == "浏览器器官不可用"
    assert result.error == "browser organ unavailable"


def test_execute_browser_publish_returns_result_when_publish_succeeds():
    result = execute_xiaohongshu_browser_publish(
        title="标题",
        body="正文",
        selector="button[type='submit']",
        image_paths=["/tmp/cover.png"],
        open_publish_page=lambda: {"session_id": "publish-session"},
        publish_to_page=lambda session_id, title, body, selector, image_paths: {
            "status": "filled",
            "filled_title": True,
            "filled_body": True,
            "publish_clicked": False,
        },
    )

    assert result.session_id == "publish-session"
    assert result.publish_result is not None
    assert result.publish_result["status"] == "filled"
    assert result.blocked_reason == ""
    assert result.error == ""


def test_execute_browser_publish_returns_error_when_publish_capability_fails():
    result = execute_xiaohongshu_browser_publish(
        title="标题",
        body="正文",
        selector="button[type='submit']",
        image_paths=[],
        open_publish_page=lambda: {"session_id": "publish-session"},
        publish_to_page=lambda session_id, title, body, selector, image_paths: (
            (_ for _ in ()).throw(BrowserCapabilityError("driver error"))
        ),
    )

    assert result.session_id == "publish-session"
    assert result.publish_result is None
    assert result.blocked_reason == "发布失败: driver error"
    assert result.error == "driver error"
