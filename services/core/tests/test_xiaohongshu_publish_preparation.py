from app.api.tool_capability_bridge import BrowserOrganUnavailable
from app.usecases.xiaohongshu_publish_preparation import (
    build_xiaohongshu_browser_publish_image_paths,
    find_xiaohongshu_publish_button,
    prepare_xiaohongshu_publish_draft,
)


def test_build_browser_publish_image_paths_prefers_existing_images():
    result = build_xiaohongshu_browser_publish_image_paths(
        {"image_paths": [" /tmp/a.png ", "", "/tmp/b.png"]},
        generate_cover_image=lambda **kwargs: None,
    )

    assert result == ["/tmp/a.png", "/tmp/b.png"]


def test_build_browser_publish_image_paths_generates_cover_when_missing():
    result = build_xiaohongshu_browser_publish_image_paths(
        {"title": "标题", "body": "正文"},
        generate_cover_image=lambda **kwargs: type("Cover", (), {"path": "/tmp/generated-cover.png"})(),
    )

    assert result == ["/tmp/generated-cover.png"]


def test_prepare_publish_draft_backfills_light_science_body_when_missing():
    result = prepare_xiaohongshu_publish_draft(
        {
            "draft_id": "draft-1",
            "title": "收到礼物却有点失落",
            "body": "",
            "opportunity_title": "#高颜值巧克力",
        }
    )

    assert result["title"] == "收到礼物却有点失落"
    assert "看到 #高颜值巧克力 的时候" in result["body"]
    assert "不是你太敏感" in result["body"]


def test_find_publish_button_returns_selector_and_closes_session():
    closed: list[str] = []

    def fake_call_browser_capability(capability, args, *, timeout_seconds=15.0):
        _ = timeout_seconds
        if capability == "browser.open":
            return {"session_id": "publish-session"}
        if capability == "browser.find_publish_button":
            return {"found": True, "selector": "button[type='submit']"}
        raise AssertionError(f"unexpected capability: {capability}")

    result = find_xiaohongshu_publish_button(
        publish_url="https://example.com/publish",
        call_browser_capability=fake_call_browser_capability,
        close_session=lambda session_id: closed.append(session_id),
    )

    assert result == "button[type='submit']"
    assert closed == ["publish-session"]


def test_find_publish_button_returns_none_when_browser_unavailable():
    result = find_xiaohongshu_publish_button(
        publish_url="https://example.com/publish",
        call_browser_capability=lambda capability, args, *, timeout_seconds=15.0: (
            (_ for _ in ()).throw(BrowserOrganUnavailable("down"))
        ),
        close_session=lambda session_id: None,
    )

    assert result is None
