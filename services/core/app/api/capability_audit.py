from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException

from app.capabilities.models import (
    CapabilityApprovalStatus,
    CapabilityJobAuditItem,
    CapabilityJobAuditResponse,
    CapabilityJobSnapshot,
    CapabilityJobStatus,
    CapabilityName,
)
from app.capabilities.queue import CapabilityQueueStore


def parse_cursor_offset(cursor: str | None) -> int:
    if cursor is None:
        return 0
    try:
        offset = int(cursor)
    except ValueError as error:
        raise HTTPException(status_code=400, detail="invalid cursor") from error
    if offset < 0:
        raise HTTPException(status_code=400, detail="invalid cursor")
    return offset


def to_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def build_job_audit_response(
    *,
    queue: CapabilityQueueStore,
    limit: int,
    status: CapabilityJobStatus | None,
    dead_letter_only: bool,
    approval_status: CapabilityApprovalStatus | None,
    approver: str | None,
    capability: CapabilityName | None,
    request_id: str | None,
    queued_from: datetime | None,
    queued_to: datetime | None,
    completed_from: datetime | None,
    completed_to: datetime | None,
    cursor: str | None,
) -> CapabilityJobAuditResponse:
    cursor_offset = parse_cursor_offset(cursor)
    queued_from_utc = to_utc(queued_from)
    queued_to_utc = to_utc(queued_to)
    completed_from_utc = to_utc(completed_from)
    completed_to_utc = to_utc(completed_to)

    snapshots = queue.list_snapshots(limit=5000, status=status, dead_letter_only=dead_letter_only)
    filtered = [
        item
        for snapshot in snapshots
        if (item := _build_audit_item(snapshot)) is not None
        and _matches_filters(
            snapshot,
            capability=capability,
            request_id=request_id,
            approval_status=approval_status,
            approver=approver,
            queued_from=queued_from_utc,
            queued_to=queued_to_utc,
            completed_from=completed_from_utc,
            completed_to=completed_to_utc,
        )
    ]

    page = filtered[cursor_offset : cursor_offset + limit]
    next_cursor = None
    if cursor_offset + limit < len(filtered):
        next_cursor = str(cursor_offset + limit)
    return CapabilityJobAuditResponse(items=page, next_cursor=next_cursor)


def _build_audit_item(snapshot: CapabilityJobSnapshot) -> CapabilityJobAuditItem | None:
    policy_version, policy_revision = _extract_policy_metadata(snapshot)
    result = snapshot.result
    return CapabilityJobAuditItem(
        request_id=snapshot.request.request_id,
        capability=snapshot.request.capability,
        status=snapshot.status,
        queued_at=snapshot.queued_at,
        completed_at=snapshot.completed_at,
        attempt=snapshot.request.attempt,
        max_attempts=snapshot.request.max_attempts,
        approval_status=snapshot.request.approval_status,
        policy_version=policy_version,
        policy_revision=policy_revision,
        executor=result.audit.executor if result is not None else None,
        ok=result.ok if result is not None else None,
        error_code=result.error_code if result is not None else None,
        dead_letter=(result.error_code == "dead_letter_exhausted_retries") if result is not None else False,
    )


def _matches_filters(
    snapshot: CapabilityJobSnapshot,
    *,
    capability: CapabilityName | None,
    request_id: str | None,
    approval_status: CapabilityApprovalStatus | None,
    approver: str | None,
    queued_from: datetime | None,
    queued_to: datetime | None,
    completed_from: datetime | None,
    completed_to: datetime | None,
) -> bool:
    if capability is not None and snapshot.request.capability != capability:
        return False
    request_id_filter = (request_id or "").strip()
    if request_id_filter and snapshot.request.request_id != request_id_filter:
        return False
    if approval_status is not None and snapshot.request.approval_status != approval_status:
        return False
    approver_filter = (approver or "").strip()
    if approver_filter:
        actor = snapshot.request.approved_by or snapshot.request.rejected_by or ""
        if actor != approver_filter:
            return False

    queued_at = _parse_snapshot_time(snapshot.queued_at)
    if queued_from is not None and (queued_at is None or queued_at < queued_from):
        return False
    if queued_to is not None and (queued_at is None or queued_at > queued_to):
        return False

    completed_at = _parse_snapshot_time(snapshot.completed_at)
    if completed_from is not None and (completed_at is None or completed_at < completed_from):
        return False
    if completed_to is not None and (completed_at is None or completed_at > completed_to):
        return False
    return True


def _parse_snapshot_time(value: str | None) -> datetime | None:
    if value is None:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _extract_policy_metadata(snapshot: CapabilityJobSnapshot) -> tuple[str | None, int | None]:
    args = snapshot.request.args if isinstance(snapshot.request.args, dict) else {}
    if snapshot.request.capability == CapabilityName.SHELL_RUN:
        version = args.get("policy_version")
        revision = args.get("policy_revision")
        return (
            version if isinstance(version, str) else None,
            int(revision) if isinstance(revision, int) else None,
        )

    file_policy = args.get("file_policy")
    if isinstance(file_policy, dict):
        version = file_policy.get("version")
        revision = file_policy.get("revision")
        return (
            version if isinstance(version, str) else None,
            int(revision) if isinstance(revision, int) else None,
        )
    return None, None
