from pathlib import Path

import pytest

from app.api.tool_capability_bridge import BrowserOrganUnavailable
from app.usecases import xiaohongshu_cover_image as cover_image


def test_generate_xiaohongshu_cover_image_writes_png(monkeypatch, tmp_path):
    calls: list[str] = []
    png_data_url = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO2pW1cAAAAASUVORK5CYII="

    def fake_call_browser_capability(capability, args, *, timeout_seconds=15.0):
        _ = timeout_seconds
        calls.append(capability)
        if capability == "browser.open":
            assert args["headless"] is True
            return {"session_id": "cover-session"}
        if capability == "browser.evaluate":
            assert args["session_id"] == "cover-session"
            return {"result": png_data_url}
        if capability == "browser.close":
            return {"status": "closed"}
        raise AssertionError(f"unexpected capability: {capability}")

    monkeypatch.setattr(cover_image, "call_browser_capability", fake_call_browser_capability)

    result = cover_image.generate_xiaohongshu_cover_image(
        title="测试标题",
        body="第一句是副标题。\n\n第二句不用上封面。",
        output_dir=str(tmp_path),
    )

    assert calls == ["browser.open", "browser.evaluate", "browser.close"]
    assert result.badge == "小晏数字人全自动运营"
    assert result.subtitle == "第一句是副标题"
    assert Path(result.path).exists()
    assert Path(result.path).suffix == ".png"


def test_generate_xiaohongshu_cover_image_raises_when_browser_unavailable(monkeypatch):
    def fake_call_browser_capability(capability, args, *, timeout_seconds=15.0):
        _ = (capability, args, timeout_seconds)
        raise BrowserOrganUnavailable("offline")

    monkeypatch.setattr(cover_image, "call_browser_capability", fake_call_browser_capability)

    with pytest.raises(cover_image.XiaohongshuCoverImageUnavailableError):
        cover_image.generate_xiaohongshu_cover_image(
            title="测试标题",
            body="测试正文",
        )
