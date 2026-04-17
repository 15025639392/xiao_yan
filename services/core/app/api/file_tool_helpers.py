from __future__ import annotations

from pathlib import Path
from typing import Any

from app.runtime_ext.runtime_config import get_runtime_config


def default_files_base_path() -> Path:
    try:
        return Path.home().resolve()
    except Exception:  # noqa: BLE001
        return Path(__file__).resolve().parents[4]


def build_file_tools():
    from app.tools.file_tools import FileTools

    config = get_runtime_config()
    granted_folders = {path: access_level for path, access_level in config.list_folder_permissions()}
    return FileTools(
        allowed_base_path=default_files_base_path(),
        folder_permissions=granted_folders,
    )


def file_policy_args() -> dict[str, Any]:
    config = get_runtime_config()
    return {"file_policy": config.get_capability_file_policy()}
