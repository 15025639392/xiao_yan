import httpx

from app.external_executors.xiaohongshu_mcp_client import (
    XiaohongshuMcpClient,
    XiaohongshuMcpClientDisabledError,
    XiaohongshuMcpClientResponseError,
)
from app.usecases.xiaohongshu_publish_via_mcp import publish_xiaohongshu_image_post_via_mcp


def test_xiaohongshu_mcp_client_maps_success_response():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == httpx.URL("http://127.0.0.1:3000/mcp")
        payload = request.read().decode("utf-8")
        assert "publish_content" in payload
        return httpx.Response(
            200,
            json={
                "jsonrpc": "2.0",
                "id": "xiao_yan_publish_image_post",
                "result": {
                    "structuredContent": {
                        "status": "submitted",
                        "message": "已提交图文发布",
                        "post_url": "https://www.xiaohongshu.com/explore/test",
                        "platform_post_id": "note_123",
                    }
                },
            },
        )

    client = XiaohongshuMcpClient(
        enabled=True,
        endpoint="http://127.0.0.1:3000/mcp",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    result = client.publish_image_post(
        title="测试标题",
        content="测试正文",
        images=["/tmp/cover.png"],
    )

    assert result.status == "submitted"
    assert result.message == "已提交图文发布"
    assert result.post_url == "https://www.xiaohongshu.com/explore/test"
    assert result.platform_post_id == "note_123"


def test_xiaohongshu_mcp_client_maps_error_payload_into_failed_status():
    def handler(request: httpx.Request) -> httpx.Response:
        _ = request
        return httpx.Response(
            200,
            json={
                "jsonrpc": "2.0",
                "id": "xiao_yan_publish_image_post",
                "error": {"message": "发布失败，请稍后重试"},
            },
        )

    client = XiaohongshuMcpClient(
        enabled=True,
        endpoint="http://127.0.0.1:3000/mcp",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    result = client.publish_image_post(
        title="测试标题",
        content="测试正文",
        images=["/tmp/cover.png"],
    )

    assert result.status == "publish_failed"
    assert "稍后重试" in result.message


def test_xiaohongshu_mcp_client_rejects_disabled_publisher():
    client = XiaohongshuMcpClient(enabled=False, endpoint=None)

    try:
        client.publish_image_post(title="测试标题", content="测试正文", images=["/tmp/cover.png"])
    except XiaohongshuMcpClientDisabledError as exc:
        assert "disabled" in str(exc)
    else:
        raise AssertionError("expected disabled client error")


def test_xiaohongshu_mcp_client_rejects_missing_result_payload():
    def handler(request: httpx.Request) -> httpx.Response:
        _ = request
        return httpx.Response(200, json={"jsonrpc": "2.0", "id": "xiao_yan_publish_image_post"})

    client = XiaohongshuMcpClient(
        enabled=True,
        endpoint="http://127.0.0.1:3000/mcp",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    try:
        client.publish_image_post(title="测试标题", content="测试正文", images=["/tmp/cover.png"])
    except XiaohongshuMcpClientResponseError as exc:
        assert "missing" in str(exc)
    else:
        raise AssertionError("expected invalid payload error")


def test_publish_xiaohongshu_image_post_via_mcp_validates_absolute_existing_paths(tmp_path):
    cover = tmp_path / "cover.png"
    cover.write_bytes(b"png")
    detail = tmp_path / "detail.png"
    detail.write_bytes(b"png")

    class _StubClient:
        def publish_image_post(self, *, title: str, content: str, images: list[str]):
            assert title == "测试标题"
            assert content == "测试正文"
            assert images == [str(cover), str(detail)]

            class _Result:
                status = "submitted"
                message = "已提交图文发布"
                post_url = "https://www.xiaohongshu.com/explore/test"
                platform_post_id = "note_123"

            return _Result()

    result = publish_xiaohongshu_image_post_via_mcp(
        title=" 测试标题 ",
        body=" 测试正文 ",
        image_paths=[str(cover), str(detail)],
        client=_StubClient(),  # type: ignore[arg-type]
    )

    assert result.status == "submitted"
    assert result.image_count == 2
    assert result.image_paths == [str(cover), str(detail)]
    assert result.post_url == "https://www.xiaohongshu.com/explore/test"


def test_publish_xiaohongshu_image_post_via_mcp_requires_existing_absolute_paths(tmp_path):
    missing = tmp_path / "missing.png"

    class _UnusedClient:
        def publish_image_post(self, *, title: str, content: str, images: list[str]):
            raise AssertionError("client should not be called")

    try:
        publish_xiaohongshu_image_post_via_mcp(
            title="测试标题",
            body="测试正文",
            image_paths=[str(missing)],
            client=_UnusedClient(),  # type: ignore[arg-type]
        )
    except ValueError as exc:
        assert "does not exist" in str(exc)
    else:
        raise AssertionError("expected missing image path validation error")
