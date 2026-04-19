from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import cast
from uuid import uuid4

from app.capabilities.models import (
    CapabilityApprovalStatus,
    CapabilityDispatchRequest,
    CapabilityJobStatus,
    CapabilityPendingItem,
    CapabilityRequest,
    CapabilityResult,
)
from app.capabilities.queue_mutations import (
    bump_attempt,
    complete_success,
    mark_dead_letter,
    reset_for_retry,
)
from app.capabilities.queue_records import CapabilityRecord

DEFAULT_MAX_ATTEMPTS = 3
MAX_ATTEMPTS_HARD_LIMIT = 20

RETRYABLE_ERROR_CODES: set[str] = {
    "execution_error",
    "timeout",
    "executor_unavailable",
    "lease_expired",
}


@dataclass(slots=True)
class ClaimPendingResult:
    items: list[CapabilityPendingItem]
    mutated: bool


def build_dispatch_record(
    payload: CapabilityDispatchRequest,
    *,
    request_id: str | None,
    risk_level: str,
    requires_approval: bool,
    queued_at: datetime,
) -> CapabilityRecord:
    request = CapabilityRequest(
        request_id=request_id or uuid4().hex,
        capability=payload.capability,
        args=payload.args,
        risk_level=risk_level,
        requires_approval=requires_approval,
        approval_status=(
            CapabilityApprovalStatus.PENDING
            if requires_approval
            else CapabilityApprovalStatus.NOT_REQUIRED
        ),
        idempotency_key=payload.idempotency_key,
        attempt=1,
        max_attempts=max(
            1,
            min(
                int(payload.max_attempts or DEFAULT_MAX_ATTEMPTS),
                MAX_ATTEMPTS_HARD_LIMIT,
            ),
        ),
        context=payload.context,
    )
    return CapabilityRecord(
        request=request,
        status=CapabilityJobStatus.PENDING,
        queued_at=queued_at,
    )


def is_retryable_failure(result: CapabilityResult) -> bool:
    if result.ok:
        return False
    code = (result.error_code or "").strip().lower()
    return code in RETRYABLE_ERROR_CODES


def mark_dead_letter_for_error(
    record: CapabilityRecord,
    *,
    finished_at: datetime,
    error_code: str,
    error_message: str,
) -> None:
    mark_dead_letter(
        record,
        finished_at=finished_at,
        error_code=error_code,
        error_message=error_message,
    )


def bump_attempt_or_dead_letter(record: CapabilityRecord, *, now: datetime) -> bool:
    if record.request.attempt >= record.request.max_attempts:
        mark_dead_letter_for_error(
            record,
            finished_at=now,
            error_code="dead_letter_exhausted_retries",
            error_message=f"retry limit reached ({record.request.attempt}/{record.request.max_attempts})",
        )
        return False
    bump_attempt(record)
    return True


def claim_pending_items(
    *,
    order: list[str],
    records: dict[str, CapabilityRecord],
    limit: int,
    lease_seconds: int,
    now: datetime,
) -> ClaimPendingResult:
    claimed: list[CapabilityPendingItem] = []
    lease_delta = timedelta(seconds=max(5, lease_seconds))
    mutated = False

    for request_id in order:
        if len(claimed) >= limit:
            break
        record = records.get(request_id)
        if record is None:
            continue
        if record.status == CapabilityJobStatus.COMPLETED:
            continue
        if record.request.approval_status == CapabilityApprovalStatus.PENDING:
            continue
        if record.request.approval_status == CapabilityApprovalStatus.REJECTED:
            continue

        if record.status == CapabilityJobStatus.IN_PROGRESS and record.lease_expires_at is not None:
            if record.lease_expires_at > now:
                continue
            if not bump_attempt_or_dead_letter(record, now=now):
                mutated = True
                continue

        record.status = CapabilityJobStatus.IN_PROGRESS
        record.lease_expires_at = now + lease_delta
        record.dead_lettered = False
        mutated = True
        claimed.append(
            CapabilityPendingItem(
                request=record.request,
                queued_at=record.queued_at.isoformat(),
                lease_expires_at=cast(datetime, record.lease_expires_at).isoformat(),
            )
        )

    return ClaimPendingResult(items=claimed, mutated=mutated)


def apply_completion_result(
    *,
    record: CapabilityRecord,
    result: CapabilityResult,
    now: datetime,
) -> None:
    if is_retryable_failure(result):
        record.last_error_code = result.error_code
        record.last_error_message = result.error_message
        if record.request.attempt >= record.request.max_attempts:
            message = result.error_message or "retry limit reached"
            mark_dead_letter_for_error(
                record,
                finished_at=now,
                error_code="dead_letter_exhausted_retries",
                error_message=message,
            )
            return
        reset_for_retry(record, result=result)
        return

    complete_success(record, result=result, completed_at=now)
