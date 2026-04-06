from __future__ import annotations

import logging
from typing import Any

from app.domain.models import BeingState, FocusMode, SelfProgrammingStatus
from app.self_programming.health_checker import HealthReport, HealthSignal


def reconstruct_candidate(job) -> object:
    """从 Job 反推一个 Candidate 对象，用于调用 plan_all。"""
    from app.self_programming.models import SelfProgrammingCandidate, SelfProgrammingTrigger

    trigger_type = SelfProgrammingTrigger.PROACTIVE
    if "[LLM]" in (job.patch_summary or ""):
        trigger_type = SelfProgrammingTrigger.HARD_FAILURE

    test_commands = []
    if job.verification and job.verification.commands:
        test_commands = job.verification.commands

    return SelfProgrammingCandidate(
        trigger=trigger_type,
        reason=job.reason,
        target_area=job.target_area,
        spec=job.spec,
        test_commands=test_commands,
    )


def finish_state(state: BeingState, job) -> BeingState:
    if job.status == SelfProgrammingStatus.APPLIED:
        thought = f"这次自我编程通过了验证，我刚补强了 {job.target_area}。"
    else:
        thought = f"这次自我编程没有通过验证，我先记住问题：{job.patch_summary or job.reason}"
    return state.model_copy(
        update={
            "focus_mode": FocusMode.AUTONOMY,
            "self_programming_job": job,
            "current_thought": thought,
        }
    )


def evaluate_health(service: Any, job: Any, logger: logging.Logger) -> HealthReport | None:
    checker = service.health_checker if hasattr(service, "health_checker") else None
    if checker is None:
        return None

    history_list = []
    recent_rollbacks = 0
    recent_conflicts = 0

    if hasattr(service, "history") and service.history is not None:
        try:
            history_list = service.history.get_recent(20)
            for entry in history_list:
                status_val = getattr(entry, "status", "")
                if hasattr(status_val, "value"):
                    status_val = status_val.value
                if status_val == "rolled_back":
                    recent_rollbacks += 1
                conflict_count = getattr(entry, "conflict_count", 0)
                if conflict_count > 0:
                    recent_conflicts += 1
        except Exception:
            pass

    signals: list[HealthSignal] = []
    if job.verification and job.verification.passed:
        signals.append(
            HealthSignal(
                source="verification",
                metric="test_pass_rate",
                value=100.0,
                unit="%",
            )
        )
    elif job.verification and not job.verification.passed:
        signals.append(
            HealthSignal(
                source="verification",
                metric="test_pass_rate",
                value=0.0,
                unit="%",
            )
        )

    report = checker.check(
        signals=signals if signals else None,
        history=history_list if history_list else None,
        recent_rollbacks=recent_rollbacks,
        recent_conflicts=recent_conflicts,
    )

    logger.info(
        f"Health check for {job.id[:12]}: "
        f"{report.summary}"
    )
    return report


def build_edits_summary(job: Any) -> str:
    edits = job.edits or []
    touched = job.touched_files or []
    if not edits and not touched:
        return job.patch_summary or job.spec[:120]

    kind_counts: dict[str, int] = {}
    for edit in edits:
        kind = getattr(edit, "kind", "replace")
        kind_counts[kind] = kind_counts.get(kind, 0) + 1

    parts = []
    if kind_counts:
        for kind, count in kind_counts.items():
            parts.append(f"{kind.upper()}×{count}")
    if touched:
        parts.append(f"文件: {', '.join(touched[:5])}")

    return " | ".join(parts) if parts else (job.patch_summary or job.spec[:120])


__all__ = [
    "reconstruct_candidate",
    "finish_state",
    "evaluate_health",
    "build_edits_summary",
]
