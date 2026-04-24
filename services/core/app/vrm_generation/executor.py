from __future__ import annotations

import subprocess
import sys
from collections.abc import Callable
from pathlib import Path


class BlenderUnavailableError(RuntimeError):
    pass


class BlenderExecutionError(RuntimeError):
    pass


class BlenderVrmExecutor:
    def __init__(self, *, blender_path: Path | None, script_path: Path, timeout_seconds: int = 180) -> None:
        self._blender_path = blender_path
        self._script_path = script_path
        self._timeout_seconds = timeout_seconds

    def export_vrm(
        self,
        *,
        input_path: Path,
        spec_path: Path,
        output_path: Path,
        log_path: Path,
        is_cancelled: Callable[[], bool] | None = None,
    ) -> None:
        command = self._build_command(input_path=input_path, spec_path=spec_path, output_path=output_path)
        self._run_command(command, output_path=output_path, log_path=log_path, is_cancelled=is_cancelled)

    def export_vrm_from_template(
        self,
        *,
        template_path: Path,
        spec_path: Path,
        output_path: Path,
        log_path: Path,
        is_cancelled: Callable[[], bool] | None = None,
    ) -> None:
        command = self._build_template_command(template_path=template_path, spec_path=spec_path, output_path=output_path)
        self._run_command(command, output_path=output_path, log_path=log_path, is_cancelled=is_cancelled)

    def _wait_for_process(
        self,
        process: subprocess.Popen[str],
        *,
        is_cancelled: Callable[[], bool] | None,
    ) -> tuple[str, str]:
        deadline_seconds = self._timeout_seconds
        elapsed = 0.0
        poll_interval = 0.05
        while process.poll() is None:
            if is_cancelled and is_cancelled():
                process.terminate()
                try:
                    return process.communicate(timeout=1)
                except subprocess.TimeoutExpired:
                    process.kill()
                    return process.communicate()
            if elapsed >= deadline_seconds:
                raise subprocess.TimeoutExpired(process.args, self._timeout_seconds)
            import time

            time.sleep(poll_interval)
            elapsed += poll_interval
        return process.communicate()

    def _run_command(
        self,
        command: list[str],
        *,
        output_path: Path,
        log_path: Path,
        is_cancelled: Callable[[], bool] | None,
    ) -> None:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        except FileNotFoundError as exc:
            raise BlenderUnavailableError("Blender executable is not available") from exc
        except PermissionError as exc:
            raise BlenderUnavailableError("Blender executable is not executable") from exc

        try:
            stdout, stderr = self._wait_for_process(process, is_cancelled=is_cancelled)
        except subprocess.TimeoutExpired as exc:
            process.kill()
            process.communicate()
            raise BlenderExecutionError("Blender execution timed out") from exc

        log_path.write_text((stdout or "") + (stderr or ""), encoding="utf-8")
        if process.returncode != 0:
            raise BlenderExecutionError(f"Blender exited with code {process.returncode}")
        if not output_path.is_file():
            raise BlenderExecutionError("Blender completed without creating output VRM")

    def _build_command(self, *, input_path: Path, spec_path: Path, output_path: Path) -> list[str]:
        if self._blender_path is None or not self._blender_path.exists():
            raise BlenderUnavailableError("Blender executable is not configured")
        if self._blender_path.suffix == ".py":
            return [
                sys.executable,
                str(self._blender_path),
                "--input",
                str(input_path),
                "--spec",
                str(spec_path),
                "--output",
                str(output_path),
            ]
        return [
            str(self._blender_path),
            "--background",
            "--python-exit-code",
            "1",
            "--python",
            str(self._script_path),
            "--",
            "--input",
            str(input_path),
            "--spec",
            str(spec_path),
            "--output",
            str(output_path),
        ]

    def _build_template_command(self, *, template_path: Path, spec_path: Path, output_path: Path) -> list[str]:
        if self._blender_path is None or not self._blender_path.exists():
            raise BlenderUnavailableError("Blender executable is not configured")
        if self._blender_path.suffix == ".py":
            return [
                sys.executable,
                str(self._blender_path),
                str(template_path),
                "--spec",
                str(spec_path),
                "--output",
                str(output_path),
            ]
        template_script = self._script_path.with_name("export_blend_vrm.py")
        return [
            str(self._blender_path),
            "--background",
            str(template_path),
            "--python-exit-code",
            "1",
            "--python",
            str(template_script),
            "--",
            "--spec",
            str(spec_path),
            "--output",
            str(output_path),
        ]
