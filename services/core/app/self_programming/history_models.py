"""
自我编程历史记录的数据模型。
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class HistoryEntryStatus(str, Enum):
    """历史条目状态。"""

    APPLIED = "applied"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


@dataclass
class HistoryEntry:
    """一条完整的自我编程历史记录。"""

    job_id: str
    target_area: str
    reason: str
    spec: str
    reason_statement: str | None = None
    direction_statement: str | None = None
    status: HistoryEntryStatus = HistoryEntryStatus.APPLIED
    patch_summary: str | None = None
    touched_files: list[str] = field(default_factory=list)
    edits_summary: list[dict] = field(default_factory=list)
    branch_name: str | None = None
    commit_hash: str | None = None
    commit_message: str | None = None
    candidate_label: str | None = None
    candidates_tried: int = 0
    selected_candidate: str | None = None
    sandbox_prevalidated: bool = False
    sandbox_duration: float = 0.0
    conflict_severity: str = "safe"
    conflict_count: int = 0
    health_score: float | None = None
    rejection_phase: str | None = None
    rejection_reason: str | None = None
    approved_at: str | None = None
    approved_by: str | None = None
    start_approved_at: str | None = None
    start_approved_by: str | None = None
    created_at: str = ""
    completed_at: str = ""

    def __post_init__(self) -> None:
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()
        if not self.completed_at and self.status != HistoryEntryStatus.APPLIED:
            self.completed_at = datetime.now(timezone.utc).isoformat()

    @classmethod
    def from_job(cls, job: Any, **overrides: Any) -> "HistoryEntry":
        status_map = {
            "applied": HistoryEntryStatus.APPLIED,
            "failed": HistoryEntryStatus.FAILED,
            "rolled_back": HistoryEntryStatus.ROLLED_BACK,
        }
        raw_status = getattr(job, "status", "")
        if hasattr(raw_status, "value"):
            raw_status = raw_status.value

        edits_summary = []
        for e in (job.edits or []):
            kind_val = getattr(e, "kind", "replace")
            if hasattr(kind_val, "value"):
                kind_str = kind_val.value
            else:
                kind_str = str(kind_val)
            edits_summary.append(
                {
                    "file": getattr(e, "file_path", ""),
                    "kind": kind_str,
                    "search": (getattr(e, "search_text", "") or "")[:60],
                }
            )

        return cls(
            job_id=job.id,
            target_area=job.target_area,
            reason=job.reason,
            reason_statement=getattr(job, "reason_statement", None),
            direction_statement=getattr(job, "direction_statement", None),
            spec=job.spec,
            status=status_map.get(str(raw_status), HistoryEntryStatus.FAILED),
            patch_summary=job.patch_summary,
            touched_files=list(job.touched_files or []),
            edits_summary=edits_summary,
            branch_name=job.branch_name,
            commit_hash=job.commit_hash,
            commit_message=job.commit_message,
            candidate_label=job.candidate_label,
            health_score=getattr(job, "health_score", None),
            rejection_phase=getattr(job, "rejection_phase", None),
            rejection_reason=getattr(job, "rejection_reason", None),
            approved_at=(
                job.approval_requested_at.isoformat()
                if getattr(job, "approval_requested_at", None) is not None
                else None
            ),
            approved_by=getattr(job, "approved_by", None),
            start_approved_at=(
                job.start_approved_at.isoformat()
                if getattr(job, "start_approved_at", None) is not None
                else None
            ),
            start_approved_by=getattr(job, "start_approved_by", None),
            created_at=datetime.now(timezone.utc).isoformat(),
            **overrides,
        )

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["status"] = self.status.value
        return data


__all__ = [
    "HistoryEntryStatus",
    "HistoryEntry",
]
