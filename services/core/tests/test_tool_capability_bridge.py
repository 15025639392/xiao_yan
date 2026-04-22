from app.api import tool_capability_bridge


def test_try_dispatch_browser_capability_returns_raw_for_browser_evaluate(monkeypatch):
    monkeypatch.setattr(tool_capability_bridge, "_has_recent_desktop_executor", lambda: True)
    monkeypatch.setattr(
        tool_capability_bridge,
        "dispatch_and_wait",
        lambda payload, timeout_seconds, poll_interval_seconds: type(
            "StubResult",
            (),
            {
                "ok": True,
                "output": {
                    "session_id": "browser-session",
                    "result": '{"status":"opened_text_to_image"}',
                    "evaluated_at": "2026-04-22T00:00:00+00:00",
                },
                "request_id": "req-evaluate",
                "error_code": None,
                "error_message": None,
            },
        )(),
    )

    result = tool_capability_bridge.try_dispatch_browser_capability(
        "browser.evaluate",
        {"session_id": "browser-session", "script": "() => 1"},
    )

    assert result is not None
    assert result["session_id"] == "browser-session"
    assert "opened_text_to_image" in result["result"]


def test_desktop_executor_recent_window_is_long_enough_for_browser_flows():
    assert tool_capability_bridge.DESKTOP_EXECUTOR_MAX_AGE_SECONDS == 60
