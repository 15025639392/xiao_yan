from __future__ import annotations

import os
import platform
import subprocess
from datetime import datetime, timezone
from functools import lru_cache
from logging import getLogger
from pathlib import Path
from typing import TypedDict

from app.config import get_service_root

logger = getLogger(__name__)

_DISABLED_VALUES = {"0", "false", "no", "off"}


class MacConsoleBootstrapStatus(TypedDict):
    state: str
    healthy: bool
    platform: str
    enabled: bool
    attempted_autofix: bool
    summary: str
    checked_at: str
    script_path: str | None
    check_exit_code: int | None
    apply_exit_code: int | None


def _is_bootstrap_enabled() -> bool:
    raw = os.getenv("MAC_CONSOLE_BOOTSTRAP_ENABLED", "1").strip().lower()
    return raw not in _DISABLED_VALUES


def _get_bootstrap_timeout_seconds() -> int:
    raw = os.getenv("MAC_CONSOLE_BOOTSTRAP_TIMEOUT_SECONDS", "180").strip()
    try:
        return max(int(raw), 5)
    except ValueError:
        logger.warning(
            "Invalid MAC_CONSOLE_BOOTSTRAP_TIMEOUT_SECONDS=%r, fallback to 180 seconds.",
            raw,
        )
        return 180


def _resolve_bootstrap_script_path() -> Path:
    configured = os.getenv("MAC_CONSOLE_BOOTSTRAP_SCRIPT", "").strip()
    if configured:
        return Path(configured).expanduser()

    repo_root = get_service_root().parents[1]
    return repo_root / "scripts" / "bootstrap_mac_console.sh"


def _run_bootstrap_command(command: list[str], timeout_seconds: int) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
    )


def _summarize_output(text: str, max_chars: int = 600) -> str:
    normalized = text.strip()
    if not normalized:
        return "(empty)"
    if len(normalized) <= max_chars:
        return normalized
    return normalized[: max_chars - 3] + "..."


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _build_status(
    *,
    state: str,
    healthy: bool,
    platform_name: str,
    enabled: bool,
    attempted_autofix: bool,
    summary: str,
    script_path: str | None = None,
    check_exit_code: int | None = None,
    apply_exit_code: int | None = None,
) -> MacConsoleBootstrapStatus:
    return {
        "state": state,
        "healthy": healthy,
        "platform": platform_name,
        "enabled": enabled,
        "attempted_autofix": attempted_autofix,
        "summary": summary,
        "checked_at": _utc_now_iso(),
        "script_path": script_path,
        "check_exit_code": check_exit_code,
        "apply_exit_code": apply_exit_code,
    }


@lru_cache(maxsize=1)
def maybe_bootstrap_mac_console_environment() -> MacConsoleBootstrapStatus:
    platform_name = platform.system()
    enabled = _is_bootstrap_enabled()

    if not enabled:
        logger.info("mac console bootstrap disabled via MAC_CONSOLE_BOOTSTRAP_ENABLED.")
        return _build_status(
            state="disabled",
            healthy=True,
            platform_name=platform_name,
            enabled=False,
            attempted_autofix=False,
            summary="mac console bootstrap disabled by environment variable.",
        )

    if platform_name != "Darwin":
        return _build_status(
            state="skipped_non_macos",
            healthy=True,
            platform_name=platform_name,
            enabled=True,
            attempted_autofix=False,
            summary="mac console bootstrap skipped on non-macOS platform.",
        )

    script_path = _resolve_bootstrap_script_path()
    if not script_path.is_file():
        logger.warning("mac console bootstrap script not found: %s", script_path)
        return _build_status(
            state="script_missing",
            healthy=False,
            platform_name=platform_name,
            enabled=True,
            attempted_autofix=False,
            summary="bootstrap script is missing; cannot self-heal console environment.",
            script_path=str(script_path),
        )

    timeout_seconds = _get_bootstrap_timeout_seconds()
    script = str(script_path)

    try:
        check_result = _run_bootstrap_command([script, "--check"], timeout_seconds)
    except Exception as error:
        logger.exception("Failed to run mac console bootstrap check.")
        return _build_status(
            state="check_error",
            healthy=False,
            platform_name=platform_name,
            enabled=True,
            attempted_autofix=False,
            summary=f"bootstrap check raised exception: {type(error).__name__}.",
            script_path=script,
        )

    if check_result.returncode == 0:
        logger.info("mac console bootstrap check passed.")
        return _build_status(
            state="check_passed",
            healthy=True,
            platform_name=platform_name,
            enabled=True,
            attempted_autofix=False,
            summary="mac console environment check passed.",
            script_path=script,
            check_exit_code=check_result.returncode,
        )

    logger.warning(
        "mac console bootstrap check failed (exit=%s). stdout=%s stderr=%s",
        check_result.returncode,
        _summarize_output(check_result.stdout),
        _summarize_output(check_result.stderr),
    )

    try:
        apply_result = _run_bootstrap_command([script], timeout_seconds)
    except Exception as error:
        logger.exception("Failed to run mac console bootstrap autofix.")
        return _build_status(
            state="autofix_error",
            healthy=False,
            platform_name=platform_name,
            enabled=True,
            attempted_autofix=True,
            summary=f"autofix raised exception: {type(error).__name__}.",
            script_path=script,
            check_exit_code=check_result.returncode,
        )

    if apply_result.returncode == 0:
        logger.info("mac console bootstrap autofix completed.")
        return _build_status(
            state="autofix_succeeded",
            healthy=True,
            platform_name=platform_name,
            enabled=True,
            attempted_autofix=True,
            summary="check failed initially; autofix completed successfully.",
            script_path=script,
            check_exit_code=check_result.returncode,
            apply_exit_code=apply_result.returncode,
        )

    logger.warning(
        "mac console bootstrap autofix failed (exit=%s). stdout=%s stderr=%s",
        apply_result.returncode,
        _summarize_output(apply_result.stdout),
        _summarize_output(apply_result.stderr),
    )
    return _build_status(
        state="autofix_failed",
        healthy=False,
        platform_name=platform_name,
        enabled=True,
        attempted_autofix=True,
        summary="check failed and autofix failed; manual intervention required.",
        script_path=script,
        check_exit_code=check_result.returncode,
        apply_exit_code=apply_result.returncode,
    )
