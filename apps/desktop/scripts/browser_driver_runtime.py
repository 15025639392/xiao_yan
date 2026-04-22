from __future__ import annotations

from browser_driver_profile import (
    prepare_browser_organ_user_data_dir,
    resolve_browser_organ_chrome_binary,
)


_PLAYWRIGHT_PROFILE_NAME = "google-chrome-playwright"


def launch_browser_organ_persistent_context(pw, *, headless: bool):
    user_data_dir = prepare_browser_organ_user_data_dir(target_name=_PLAYWRIGHT_PROFILE_NAME)
    launch_kwargs = {
        "headless": headless,
        "args": [
            "--no-first-run",
            "--no-default-browser-check",
        ],
    }

    executable_path = resolve_browser_organ_chrome_binary()
    if executable_path:
        launch_kwargs["executable_path"] = executable_path
    else:
        launch_kwargs["channel"] = "chrome"

    return pw.chromium.launch_persistent_context(str(user_data_dir), **launch_kwargs)
