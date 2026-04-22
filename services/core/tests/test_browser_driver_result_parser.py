from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load_module():
    module_path = (
        Path(__file__).resolve().parents[3]
        / "apps"
        / "desktop"
        / "scripts"
        / "browser_driver_result_parser.py"
    )
    spec = importlib.util.spec_from_file_location("browser_driver_result_parser", module_path)
    if spec is None or spec.loader is None:
        raise AssertionError("failed to load browser_driver_result_parser")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_browser_driver_module():
    scripts_dir = Path(__file__).resolve().parents[3] / "apps" / "desktop" / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    spec = importlib.util.spec_from_file_location("browser_driver", scripts_dir / "browser_driver.py")
    if spec is None or spec.loader is None:
        raise AssertionError("failed to load browser_driver")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_browser_driver_scripts_module():
    scripts_dir = Path(__file__).resolve().parents[3] / "apps" / "desktop" / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    spec = importlib.util.spec_from_file_location("browser_driver_scripts", scripts_dir / "browser_driver_scripts.py")
    if spec is None or spec.loader is None:
        raise AssertionError("failed to load browser_driver_scripts")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_parse_evaluate_result_accepts_dict():
    module = _load_module()

    result = module.parse_evaluate_result({"status": "filled", "filled_title": True})

    assert result == {"status": "filled", "filled_title": True}


def test_parse_evaluate_result_decodes_json_string_object():
    module = _load_module()

    result = module.parse_evaluate_result(
        '{"status":"awaiting_image_upload","filled_title":false,"filled_body":false}'
    )

    assert result == {
        "status": "awaiting_image_upload",
        "filled_title": False,
        "filled_body": False,
    }


def test_parse_evaluate_result_rejects_non_json_string():
    module = _load_module()

    try:
        module.parse_evaluate_result("plain text error")
    except ValueError as exc:
        assert "non-JSON str" in str(exc)
    else:
        raise AssertionError("expected ValueError for non-JSON string result")


def test_cmd_publish_accepts_json_string_fill_result():
    browser_driver = _load_browser_driver_module()
    daemon = browser_driver.DriverDaemon("/tmp/browser-driver-test.sock")

    class DummyPage:
        url = "https://creator.xiaohongshu.com/publish/publish"

        def __init__(self):
            self.evaluate_calls = 0

        def is_closed(self):
            return False

        def inner_text(self, selector, timeout=3000):
            _ = (selector, timeout)
            return "发布页"

        def evaluate(self, script, timeout=None):
            _ = (script, timeout)
            self.evaluate_calls += 1
            return '{"status":"awaiting_image_upload","filled_title":false,"filled_body":false}'

        def wait_for_timeout(self, ms):
            _ = ms
            return None

        def click(self, selector, timeout=10000):
            _ = (selector, timeout)
            return None

    page = DummyPage()
    daemon._resolve_session = lambda session_id: type("Session", (), {"page": page})()
    browser_driver.build_fill_script = lambda title, body: "fake-script"

    result = daemon._cmd_publish(
        {
            "session_id": "test-session",
            "title": "标题",
            "body": "正文",
            "publish_selector": "",
            "image_paths": [],
        }
    )

    assert result["status"] == "awaiting_image_upload"
    assert result["filled_title"] is False
    assert result["filled_body"] is False
    assert "error" not in result
    assert page.evaluate_calls >= 3


def test_build_fill_script_preserves_multiline_body_paragraphs():
    module = _load_browser_driver_scripts_module()

    script = module.build_fill_script(title="标题", body="第一段\n\n第二段\n第三行")

    assert "createParagraphNodes" in script
    assert 'setEditableValue(bodyField, payload.body, { multiline: true })' in script
    assert 'inputType: multiline ? "insertParagraph" : "insertText"' in script
