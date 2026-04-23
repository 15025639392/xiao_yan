from app.api.tool_capability_bridge import BrowserCapabilityError, BrowserOrganUnavailable
from app.usecases.xiaohongshu_browser_publish_executor import execute_xiaohongshu_browser_publish


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
        selector="",
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
        selector="",
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


def test_execute_browser_publish_maps_missing_reusable_cdp_endpoint_on_open():
    result = execute_xiaohongshu_browser_publish(
        title="标题",
        body="正文",
        selector="",
        image_paths=[],
        open_publish_page=lambda: (_ for _ in ()).throw(
            BrowserCapabilityError('driver error: {"error": "browser organ chrome did not expose a reusable cdp endpoint"}')
        ),
        publish_to_page=lambda session_id, title, body, selector, image_paths: {},
    )

    assert result.session_id == ""
    assert result.publish_result is None
    assert result.blocked_reason == "浏览器器官未暴露可复用调试端口"
    assert result.error == "打开发布页失败: 浏览器器官未暴露可复用调试端口"


def test_execute_browser_publish_maps_missing_reusable_cdp_endpoint_on_publish():
    result = execute_xiaohongshu_browser_publish(
        title="标题",
        body="正文",
        selector="",
        image_paths=[],
        open_publish_page=lambda: {"session_id": "publish-session"},
        publish_to_page=lambda session_id, title, body, selector, image_paths: (
            (_ for _ in ()).throw(
                BrowserCapabilityError('driver error: {"error": "browser organ chrome did not expose a reusable cdp endpoint"}')
            )
        ),
    )

    assert result.session_id == "publish-session"
    assert result.publish_result is None
    assert result.blocked_reason == "浏览器器官未暴露可复用调试端口"
    assert result.error == "发布失败: 浏览器器官未暴露可复用调试端口"
