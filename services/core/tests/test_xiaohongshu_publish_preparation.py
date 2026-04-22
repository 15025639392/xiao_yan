from app.api.tool_capability_bridge import BrowserCapabilityError, BrowserOrganUnavailable
from app.usecases.xiaohongshu_publish_preparation import (
    build_xiaohongshu_browser_publish_image_paths,
    find_xiaohongshu_publish_button,
    prepare_xiaohongshu_text_image_cards_for_draft,
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


def test_prepare_text_image_cards_for_draft_returns_browser_unavailable_message():
    result = prepare_xiaohongshu_text_image_cards_for_draft(
        {"title": "标题", "body": "正文"},
        autofill_cards=lambda **kwargs: (_ for _ in ()).throw(BrowserCapabilityError("driver error")),
    )

    assert result is not None
    assert result["status"] == "browser_unavailable"
    assert "浏览器器官不可用" in result["message"]


def test_prepare_text_image_cards_for_draft_returns_focus_for_generation():
    result = prepare_xiaohongshu_text_image_cards_for_draft(
        {"title": "标题", "body": "第一段\n\n第二段"},
        autofill_cards=lambda **kwargs: type(
            "StubResult",
            (),
            {
                "status": "submitted_generation",
                "filled_cards": 3,
                "message": "ok",
            },
        )(),
    )

    assert result is not None
    assert result["status"] == "submitted_generation"
    assert "触发生成图片" in result["focus"]
