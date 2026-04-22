from __future__ import annotations

import json
import os
import subprocess
import time
import shutil
import urllib.request
from pathlib import Path


_CDP_BASE_URL = "http://127.0.0.1:9222"
_CHROME_BINARY = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
_DEFAULT_PROFILE_NAME = "Default"
_ROOT_FILES_TO_COPY = ("Local State", "First Run", "Last Version")
_PROFILE_IGNORE_NAMES = {
    "Cache",
    "Code Cache",
    "Crashpad",
    "DawnCache",
    "GPUCache",
    "GrShaderCache",
    "GraphiteDawnCache",
    "ShaderCache",
    "SingletonCookie",
    "SingletonLock",
    "SingletonSocket",
}


def resolve_browser_cdp_endpoint(base_url: str = _CDP_BASE_URL) -> str | None:
    try:
        with urllib.request.urlopen(f"{base_url}/json/version", timeout=2) as response:
            payload = json.loads(response.read())
    except Exception:
        return None

    websocket_url = payload.get("webSocketDebuggerUrl")
    if not isinstance(websocket_url, str) or not websocket_url:
        return None
    return base_url


def resolve_browser_organ_chrome_binary() -> str | None:
    return _CHROME_BINARY if Path(_CHROME_BINARY).exists() else None


def ensure_browser_organ_chrome_running(base_url: str = _CDP_BASE_URL) -> None:
    if resolve_browser_cdp_endpoint(base_url) is not None:
        return

    user_data_dir = prepare_browser_organ_user_data_dir()
    devnull = open(os.devnull, "w")
    try:
        subprocess.Popen(
            [
                _CHROME_BINARY,
                f"--user-data-dir={user_data_dir}",
                "--remote-debugging-port=9222",
                "--no-first-run",
                "--no-default-browser-check",
                "about:blank",
            ],
            stdout=devnull,
            stderr=devnull,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
        )
    finally:
        devnull.close()

    for _ in range(50):
        if resolve_browser_cdp_endpoint(base_url) is not None:
            return
        time.sleep(0.1)

    raise RuntimeError("failed to start browser organ chrome with cdp endpoint")


def prepare_browser_organ_user_data_dir(*, target_name: str = "google-chrome") -> Path:
    target_root = _browser_organ_user_data_dir(target_name=target_name)
    if _is_bootstrapped(target_root):
        return target_root

    target_root.mkdir(parents=True, exist_ok=True)
    source_root = _google_chrome_user_data_dir()
    if not source_root.exists():
        (target_root / _DEFAULT_PROFILE_NAME).mkdir(parents=True, exist_ok=True)
        return target_root

    for name in _ROOT_FILES_TO_COPY:
        source_file = source_root / name
        if source_file.exists():
            shutil.copy2(source_file, target_root / name)

    source_profile = source_root / _detect_last_used_profile(source_root)
    target_profile = target_root / _DEFAULT_PROFILE_NAME
    if source_profile.exists():
        shutil.copytree(
            source_profile,
            target_profile,
            dirs_exist_ok=True,
            ignore=_ignore_profile_entries,
        )
    else:
        target_profile.mkdir(parents=True, exist_ok=True)

    return target_root


def _browser_organ_user_data_dir(*, target_name: str) -> Path:
    return Path.home() / ".xiao_yan" / "browser-organ" / target_name


def _google_chrome_user_data_dir() -> Path:
    return Path.home() / "Library" / "Application Support" / "Google" / "Chrome"


def _is_bootstrapped(target_root: Path) -> bool:
    return (target_root / _DEFAULT_PROFILE_NAME).exists()


def _detect_last_used_profile(source_root: Path) -> str:
    local_state_path = source_root / "Local State"
    if not local_state_path.exists():
        return _DEFAULT_PROFILE_NAME

    try:
        payload = json.loads(local_state_path.read_text(encoding="utf-8"))
    except Exception:
        return _DEFAULT_PROFILE_NAME

    profile_state = payload.get("profile")
    if not isinstance(profile_state, dict):
        return _DEFAULT_PROFILE_NAME
    last_used = profile_state.get("last_used")
    if not isinstance(last_used, str) or not last_used.strip():
        return _DEFAULT_PROFILE_NAME
    return last_used.strip()


def _ignore_profile_entries(_path: str, names: list[str]) -> set[str]:
    ignored = {name for name in names if name in _PROFILE_IGNORE_NAMES}
    ignored.update(name for name in names if name.endswith(".lock"))
    return ignored
