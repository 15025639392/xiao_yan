from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable, Protocol

from app.capabilities.models import (
    CapabilityApprovalAction,
    CapabilityApprovalStatus,
    CapabilityJobSnapshot,
    CapabilityJobStatus,
)


class CapabilityRecordView(Protocol):
    request: Any
    status: CapabilityJobStatus
    queued_at: datetime
    completed_at: datetime | None
    result: Any
    dead_lettered: bool


def build_job_snapshot(record: CapabilityRecordView) -> CapabilityJobSnapshot:
    return CapabilityJobSnapshot(
        request=record.request,
        status=record.status,
        queued_at=record.queued_at.isoformat(),
        completed_at=record.completed_at.isoformat() if record.completed_at else None,
        result=record.result,
    )


def list_pending_approval_snapshots(
    *,
    order: list[str],
    records: dict[str, CapabilityRecordView],
    limit: int,
) -> list[CapabilityJobSnapshot]:
    requested = max(1, min(int(limit), 500))
    snapshots: list[CapabilityJobSnapshot] = []
    for request_id in reversed(order):
        if len(snapshots) >= requested:
            break
        record = records.get(request_id)
        if record is None:
            continue
        if record.status != CapabilityJobStatus.PENDING:
            continue
        if record.request.approval_status != CapabilityApprovalStatus.PENDING:
            continue
        snapshots.append(build_job_snapshot(record))
    return snapshots


def list_job_snapshots(
    *,
    order: list[str],
    records: dict[str, CapabilityRecordView],
    limit: int,
    status: CapabilityJobStatus | None,
    dead_letter_only: bool,
) -> list[CapabilityJobSnapshot]:
    requested = max(1, min(int(limit), 5000))
    snapshots: list[CapabilityJobSnapshot] = []
    for request_id in reversed(order):
        if len(snapshots) >= requested:
            break
        record = records.get(request_id)
        if record is None:
            continue
        if status is not None and record.status != status:
            continue
        if dead_letter_only and not record.dead_lettered:
            continue
        snapshots.append(build_job_snapshot(record))
    return snapshots


def compute_status_counts(records: Iterable[CapabilityRecordView]) -> dict[str, int]:
    pending = 0
    pending_approval = 0
    in_progress = 0
    completed = 0
    dead_letter = 0
    for record in records:
        if record.status == CapabilityJobStatus.PENDING:
            pending += 1
            if record.request.approval_status == CapabilityApprovalStatus.PENDING:
                pending_approval += 1
        elif record.status == CapabilityJobStatus.IN_PROGRESS:
            in_progress += 1
        elif record.status == CapabilityJobStatus.COMPLETED:
            completed += 1
            if record.dead_lettered:
                dead_letter += 1
    return {
        "pending": pending,
        "pending_approval": pending_approval,
        "in_progress": in_progress,
        "completed": completed,
        "dead_letter": dead_letter,
    }


def append_approval_event(
    events: list[dict[str, Any]],
    *,
    request: Any,
    action: CapabilityApprovalAction,
    approver: str,
    reason: str | None,
    decided_at: str,
) -> list[dict[str, Any]]:
    next_events = list(events)
    next_events.append(
        {
            "request_id": request.request_id,
            "capability": request.capability.value,
            "action": action.value,
            "approver": approver,
            "reason": reason,
            "decided_at": decided_at,
        }
    )
    if len(next_events) > 2000:
        next_events = next_events[-2000:]
    return next_events


def filter_approval_events(
    events: list[dict[str, Any]],
    *,
    limit: int,
    action: CapabilityApprovalAction | None,
    approver: str | None,
    capability: str | None,
    request_id: str | None,
) -> list[dict[str, Any]]:
    requested = max(1, min(int(limit), 500))
    approver_filter = (approver or "").strip()
    capability_filter = (capability or "").strip()
    request_id_filter = (request_id or "").strip()

    results: list[dict[str, Any]] = []
    for event in reversed(events):
        if len(results) >= requested:
            break
        if action is not None and event.get("action") != action.value:
            continue
        if approver_filter and event.get("approver") != approver_filter:
            continue
        if capability_filter and event.get("capability") != capability_filter:
            continue
        if request_id_filter and event.get("request_id") != request_id_filter:
            continue
        results.append(dict(event))
    return results
