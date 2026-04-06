from __future__ import annotations

import os
import subprocess
from pathlib import Path

from app.domain.models import EditKind, SelfProgrammingVerification


def apply_edits(
    workspace_root: Path,
    edits,
    backups: dict[Path, str],
    touched_files: list[str],
) -> None:
    for edit in edits:
        path = workspace_root / edit.file_path

        if getattr(edit, "kind", EditKind.REPLACE) == EditKind.CREATE:
            if not edit.file_content:
                raise ValueError(f"CREATE edit missing file_content for {edit.file_path}")
            path.parent.mkdir(parents=True, exist_ok=True)
            original = ""
            if path.exists():
                original = path.read_text(encoding="utf-8")
            backups.setdefault(path, original)
            path.write_text(edit.file_content, encoding="utf-8")
            if edit.file_path not in touched_files:
                touched_files.append(edit.file_path)
            continue

        if getattr(edit, "kind", EditKind.REPLACE) == EditKind.INSERT:
            original = path.read_text(encoding="utf-8")
            if not edit.insert_after or edit.insert_after not in original:
                raise ValueError(f"insert_after anchor not found in {edit.file_path}")
            backups.setdefault(path, original)
            insert_pos = original.index(edit.insert_after) + len(edit.insert_after)
            updated = original[:insert_pos] + edit.replace_text + original[insert_pos:]
            path.write_text(updated, encoding="utf-8")
            if edit.file_path not in touched_files:
                touched_files.append(edit.file_path)
            continue

        original = path.read_text(encoding="utf-8")
        search_key = edit.search_text or ""
        replace_val = edit.replace_text or ""
        if search_key not in original:
            raise ValueError(f"search text not found in {edit.file_path}")
        updated = original.replace(search_key, replace_val, 1)
        backups.setdefault(path, original)
        path.write_text(updated, encoding="utf-8")
        if edit.file_path not in touched_files:
            touched_files.append(edit.file_path)


def run_verification(workspace_root: Path, commands: list[str]) -> SelfProgrammingVerification:
    outputs: list[str] = []
    passed = True

    for command in commands:
        result = subprocess.run(
            command,
            shell=True,
            cwd=workspace_root,
            capture_output=True,
            text=True,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )
        combined = "\n".join(part.strip() for part in (result.stdout, result.stderr) if part.strip())
        outputs.append(f"$ {command}\n{combined}".strip())
        if result.returncode != 0:
            passed = False
            break

    summary = "\n\n".join(outputs).strip() or "没有运行验证命令。"
    return SelfProgrammingVerification(
        commands=commands,
        passed=passed,
        summary=summary,
    )


def restore_files(backups: dict[Path, str]) -> None:
    for path, content in backups.items():
        if content:
            path.write_text(content, encoding="utf-8")
        elif path.exists():
            path.unlink()

