from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from app.self_programming.rollback_models import DiffSnapshot, RollbackPlan, RollbackResult, RollbackStatus
from app.utils.process_utils import format_command_output, run_command


def collect_snapshot_files(job: Any, extra_files: list[str] | None = None) -> set[str]:
    file_set: set[str] = set()

    touched = getattr(job, "touched_files", None) or []
    for fp in touched:
        file_set.add(fp)

    edits = getattr(job, "edits", None) or []
    for edit in edits:
        fp = getattr(edit, "file_path", None)
        if fp:
            file_set.add(fp)

    if extra_files:
        file_set.update(extra_files)

    return file_set


def take_diff_snapshots(workspace_root: Path, file_paths: set[str]) -> list[DiffSnapshot]:
    snapshots: list[DiffSnapshot] = []
    for fp in sorted(file_paths):
        snapshots.append(DiffSnapshot.from_path(fp, workspace_root))
    return snapshots


def detect_dependent_jobs(
    *,
    job_id: str,
    target_files: set[str],
    applied_history: list[Any] | None = None,
) -> list[str]:
    if not target_files or not applied_history:
        return []

    dependents: list[str] = []
    target_index = -1

    for idx, job in enumerate(applied_history):
        jid = getattr(job, "id", "") or getattr(job, "job_id", "")
        if jid == job_id:
            target_index = idx
            break

    check_from = 0 if target_index == -1 else target_index + 1

    for job in applied_history[check_from:]:
        job_files = set(getattr(job, "touched_files", []) or [])
        if target_files & job_files:
            jid = getattr(job, "id", "") or getattr(job, "job_id", "")
            if jid and jid != job_id:
                dependents.append(jid)

    return dependents


def restore_from_snapshots(
    *,
    workspace_root: Path,
    snapshots: list[DiffSnapshot],
) -> tuple[list[str], list[str]]:
    restored: list[str] = []
    failed: list[str] = []

    for snapshot in snapshots:
        try:
            full_path = workspace_root / snapshot.file_path

            if snapshot.file_existed:
                if full_path.exists():
                    full_path.read_text(encoding="utf-8")
                    full_path.write_text(snapshot.original_content, encoding="utf-8")
                    restored.append(snapshot.file_path)
                else:
                    full_path.parent.mkdir(parents=True, exist_ok=True)
                    full_path.write_text(snapshot.original_content, encoding="utf-8")
                    restored.append(snapshot.file_path)
            else:
                if full_path.exists():
                    full_path.unlink()
                    restored.append(snapshot.file_path)
                else:
                    restored.append(snapshot.file_path)

        except Exception:
            failed.append(snapshot.file_path)

    return restored, failed


def compute_rollback_status(restored: list[str], failed: list[str]) -> RollbackStatus:
    if failed and restored:
        return RollbackStatus.PARTIAL
    if failed:
        return RollbackStatus.FAILED
    return RollbackStatus.SUCCESS


def run_post_rollback_verification(
    workspace_root: Path,
    commands: list[str],
) -> tuple[bool, str]:
    outputs: list[str] = []
    all_passed = True

    for cmd in commands:
        try:
            result = run_command(
                cmd,
                shell=True,
                cwd=workspace_root,
                timeout=60,
                extra_env={"PYTHONDONTWRITEBYTECODE": "1"},
            )
            outputs.append(format_command_output(cmd, result.stdout, result.stderr))
            if result.returncode != 0:
                all_passed = False
                break
        except subprocess.TimeoutExpired:
            outputs.append(f"$ [TIMEOUT] {cmd}")
            all_passed = False
            break
        except Exception as exc:
            outputs.append(f"$ [ERROR] {cmd} → {exc}")
            all_passed = False
            break

    return all_passed, "\n\n".join(outputs)


def build_rollback_recommendation(
    status: RollbackStatus,
    plan: RollbackPlan,
    failed: list[str],
    verification_passed: bool | None,
) -> str:
    parts: list[str] = []

    if status == RollbackStatus.SUCCESS:
        parts.append("回滚成功，系统应已恢复到补丁前的状态。")
        if plan.dependent_job_ids:
            parts.append(
                f"注意：有 {len(plan.dependent_job_ids)} 个后续 Job 可能受影响，建议检查是否需要一并回滚。"
            )
    elif status == RollbackStatus.PARTIAL:
        parts.append(f"部分回滚成功。{len(failed)} 个文件还原失败：{', '.join(failed)}")
        parts.append("建议手动检查这些文件的完整性。")
    elif status == RollbackStatus.FAILED:
        parts.append("回滚全部失败。建议使用 Git 进行粗粒度恢复：")
        parts.append("  git checkout -- .      # 丢弃未提交更改")
        parts.append("  git reset --hard HEAD~1  # 回退最后一个 commit")

    if verification_passed is False:
        parts.append("回滚后验证仍未通过，问题可能不在此补丁中，或原始代码本身就有缺陷。")
    elif verification_passed is True:
        parts.append("回滚后验证通过，确认系统已恢复健康状态。")

    return "\n".join(parts)


def build_rollback_statistics(history: list[RollbackResult]) -> dict[str, Any]:
    total = len(history)
    if total == 0:
        return {"total_rollbacks": 0}

    by_reason: dict[str, int] = {}
    by_status: dict[str, int] = {}
    total_restored = 0
    total_failed = 0
    verification_pass_rate = 0
    verified_count = 0

    for r in history:
        reason_key = r.plan.reason.value
        by_reason[reason_key] = by_reason.get(reason_key, 0) + 1
        status_key = r.status.value
        by_status[status_key] = by_status.get(status_key, 0) + 1
        total_restored += len(r.restored_files)
        total_failed += len(r.failed_files)
        if r.verification_passed is not None:
            verified_count += 1
            if r.verification_passed:
                verification_pass_rate += 1

    return {
        "total_rollbacks": total,
        "by_reason": by_reason,
        "by_status": by_status,
        "total_files_restored": total_restored,
        "total_files_failed": total_failed,
        "verification_pass_rate": (
            round(verification_pass_rate / verified_count * 100, 1)
            if verified_count > 0
            else None
        ),
    }
