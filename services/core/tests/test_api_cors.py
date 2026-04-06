from fastapi.testclient import TestClient

from app.main import app


def _preflight(origin: str) -> tuple[int, str]:
    client = TestClient(app)
    response = client.options(
        "/chat",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    return response.status_code, response.text


def test_cors_preflight_allows_localhost_any_port():
    status, _ = _preflight("http://localhost:3000")
    assert status == 200


def test_cors_preflight_allows_null_origin_for_desktop_webview():
    status, _ = _preflight("null")
    assert status == 200


def test_cors_preflight_still_blocks_external_origins():
    status, body = _preflight("https://evil.example.com")
    assert status == 400
    assert body == "Disallowed CORS origin"
