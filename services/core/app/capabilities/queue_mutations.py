from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol

from app.capabilities.models import (
    CapabilityApprovalStatus,
    CapabilityAudit,
    CapabilityJobStatus,
    CapabilityResult,
)


class CapabilityMutableRecord(Protocol):
    request: Any
    status: CapabilityJobStatus
    queued_at: datetime
    lease_expires_at: datetime | None
    completed_at: datetime | None
    result: CapabilityResult | None
    dead_lettered: bool
    last_error_code: str | None
    last_error_message: str | None


def mark_dead_letter(
    record: CapabilityMutableRecord,
    *,
    finished_at: datetime,
    error_code: str,
    error_message: str,
) -> None:
    record.status = CapabilityJobStatus.COMPLETED
    record.lease_expires_at = None
    record.completed_at = finished_at
    record.dead_lettered = True
    record.last_error_code = error_code
    record.last_error_message = error_message
    record.result = CapabilityResult(
        request_id=record.request.request_id,
        ok=False,
        error_code=error_code,
        error_message=error_message,
        audit=CapabilityAudit(
            executor="core",
            started_at=finished_at.isoformat(),
            finished_at=finished_at.isoformat(),
            duration_ms=0,
        ),
    )


def bump_attempt(record: CapabilityMutableRecord) -> None:
    record.request = record.request.model_copy(
        update={"attempt": int(record.request.attempt) + 1},
        deep=True,
    )


def reset_for_retry(record: CapabilityMutableRecord, *, result: CapabilityResult) -> None:
    record.last_error_code = result.error_code
    record.last_error_message = result.error_message
    bump_attempt(record)
    record.status = CapabilityJobStatus.PENDING
    record.lease_expires_at = None
    record.completed_at = None
    record.result = None
    record.dead_lettered = False


def complete_success(record: CapabilityMutableRecord, *, result: CapabilityResult, completed_at: datetime) -> None:
    record.result = result
    record.status = CapabilityJobStatus.COMPLETED
    record.completed_at = completed_at
    record.lease_expires_at = None
    record.dead_lettered = False
    record.last_error_code = result.error_code
    record.last_error_message = result.error_message


def approve_record(
    record: CapabilityMutableRecord,
    *,
    approver: str,
    decided_at: str,
) -> None:
    record.request = record.request.model_copy(
        update={
            "approval_status": CapabilityApprovalStatus.APPROVED,
            "approved_by": approver,
            "approved_at": decided_at,
        },
        deep=True,
    )


def reject_record(
    record: CapabilityMutableRecord,
    *,
    approver: str,
    reason: str,
    finished_at: datetime,
    decided_at: str,
) -> None:
    record.request = record.request.model_copy(
        update={
            "approval_status": CapabilityApprovalStatus.REJECTED,
            "rejected_by": approver,
            "rejected_at": decided_at,
            "rejection_reason": reason,
        },
        deep=True,
    )
    record.status = CapabilityJobStatus.COMPLETED
    record.lease_expires_at = None
    record.completed_at = finished_at
    record.dead_lettered = False
    record.last_error_code = "approval_rejected"
    record.last_error_message = reason
    record.result = CapabilityResult(
        request_id=record.request.request_id,
        ok=False,
        error_code="approval_rejected",
        error_message=reason,
        audit=CapabilityAudit(
            executor="core",
            started_at=finished_at.isoformat(),
            finished_at=finished_at.isoformat(),
            duration_ms=0,
        ),
    )


def requeue_dead_letter(record: CapabilityMutableRecord) -> None:
    record.status = CapabilityJobStatus.PENDING
    record.lease_expires_at = None
    record.completed_at = None
    record.result = None
    record.dead_lettered = False
    record.last_error_code = None
    record.last_error_message = None
    record.request = record.request.model_copy(update={"attempt": 1}, deep=True)
