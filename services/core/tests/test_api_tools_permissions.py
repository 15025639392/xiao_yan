import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.runtime_ext.runtime_config import get_runtime_config


def test_tools_read_file_uses_chat_folder_permissions():
    config = get_runtime_config()
    config.clear_folder_permissions()

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            folder = Path(tmpdir).resolve()
            target = folder / "external.txt"
            target.write_text("external content", encoding="utf-8")

            client = TestClient(app)

            denied = client.get("/tools/files/read", params={"path": str(target)})
            assert denied.status_code == 200
            assert "error" in denied.json()

            config.set_folder_permission(str(folder), "read_only")

            allowed = client.get("/tools/files/read", params={"path": str(target)})
            assert allowed.status_code == 200
            assert "error" not in allowed.json()
            assert allowed.json()["path"] == str(target)
            assert allowed.json()["line_count"] == 1
    finally:
        config.clear_folder_permissions()
