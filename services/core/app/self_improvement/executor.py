import os
import subprocess
from pathlib import Path

from app.domain.models import (
    SelfImprovementJob,
    SelfImprovementStatus,
    SelfImprovementVerification,
)


class SelfImprovementExecutor:
    def __init__(self, workspace_root: Path) -> None:
        self.workspace_root = workspace_root
        self._backups: dict[str, dict[Path, str]] = {}

    def apply(self, job: SelfImprovementJob) -> SelfImprovementJob:
        if not job.test_edits and not job.edits:
            return job.model_copy(
                update={
                    "status": SelfImprovementStatus.FAILED,
                    "patch_summary": "没有可执行的补丁计划。",
                }
            )

        backups: dict[Path, str] = {}
        touched_files: list[str] = []

        try:
            self._apply_edits(job.test_edits, backups, touched_files)
            red_verification = None
            if job.test_edits:
                red_verification = self._run_verification(
                    [] if job.verification is None else job.verification.commands
                )
                if red_verification.passed:
                    raise ValueError("红灯验证没有失败，测试没有锁住问题。")

            self._apply_edits(job.edits, backups, touched_files)
        except Exception as exc:
            self._restore_files(backups)
            return job.model_copy(
                update={
                    "status": SelfImprovementStatus.FAILED,
                    "patch_summary": f"补丁应用失败：{exc}",
                    "touched_files": [],
                }
            )

        self._backups[job.id] = backups
        return job.model_copy(
            update={
                "status": SelfImprovementStatus.VERIFYING,
                "patch_summary": f"已修改 {', '.join(touched_files)}",
                "red_verification": red_verification,
                "touched_files": touched_files,
            }
        )

    def verify(self, job: SelfImprovementJob) -> SelfImprovementJob:
        verification = self._run_verification(
            [] if job.verification is None else job.verification.commands
        )
        passed = verification.passed
        if not passed:
            self._restore_job_files(job.id)

        self._backups.pop(job.id, None)
        return job.model_copy(
            update={
                "status": (
                    SelfImprovementStatus.APPLIED if passed else SelfImprovementStatus.FAILED
                ),
                "verification": verification,
            }
        )

    def _restore_job_files(self, job_id: str) -> None:
        backups = self._backups.get(job_id, {})
        self._restore_files(backups)

    def _apply_edits(
        self,
        edits,
        backups: dict[Path, str],
        touched_files: list[str],
    ) -> None:
        for edit in edits:
            path = self.workspace_root / edit.file_path
            original = path.read_text(encoding="utf-8")
            if edit.search_text not in original:
                raise ValueError(f"search text not found in {edit.file_path}")
            updated = original.replace(edit.search_text, edit.replace_text, 1)
            backups.setdefault(path, original)
            path.write_text(updated, encoding="utf-8")
            if edit.file_path not in touched_files:
                touched_files.append(edit.file_path)

    def _run_verification(self, commands: list[str]) -> SelfImprovementVerification:
        outputs: list[str] = []
        passed = True

        for command in commands:
            result = subprocess.run(
                command,
                shell=True,
                cwd=self.workspace_root,
                capture_output=True,
                text=True,
                env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
            )
            combined = "\n".join(
                part.strip() for part in (result.stdout, result.stderr) if part.strip()
            )
            outputs.append(f"$ {command}\n{combined}".strip())
            if result.returncode != 0:
                passed = False
                break

        summary = "\n\n".join(outputs).strip() or "没有运行验证命令。"
        return SelfImprovementVerification(
            commands=commands,
            passed=passed,
            summary=summary,
        )

    def _restore_files(self, backups: dict[Path, str]) -> None:
        for path, content in backups.items():
            path.write_text(content, encoding="utf-8")
