from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Mapping


def merged_env(extra_env: Mapping[str, str] | None = None) -> dict[str, str]:
    env = dict(os.environ)
    if extra_env:
        env.update(extra_env)
    return env


def run_command(
    command: list[str] | str,
    *,
    cwd: Path,
    shell: bool = False,
    timeout: float | None = None,
    extra_env: Mapping[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        shell=shell,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=timeout,
        env=merged_env(extra_env),
    )


def format_command_output(command: str, stdout: str | None, stderr: str | None) -> str:
    combined = "\n".join(
        part.strip()
        for part in (stdout, stderr)
        if part and part.strip()
    )
    return f"$ {command}\n{combined}".strip()


__all__ = [
    "merged_env",
    "run_command",
    "format_command_output",
]
