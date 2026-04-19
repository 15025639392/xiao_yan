from __future__ import annotations

from fastapi import HTTPException

from app.capabilities.models import (
    CapabilityApprovalAction,
    CapabilityApprovalDecisionResponse,
    CapabilityApprovalHistoryItem,
    CapabilityApprovalHistoryResponse,
    CapabilityApprovalPendingItem,
    CapabilityApprovalPendingResponse,
    CapabilityCompleteResponse,
    CapabilityDispatchRequest,
    CapabilityDispatchResponse,
    CapabilityJobStatus,
    CapabilityPendingResponse,
    CapabilityQueueStatusResponse,
    CapabilityResult,
    CapabilityJobSnapshot,
)
from app.capabilities.queue import CapabilityQueueStore


def dispatch_capability_response(
    queue: CapabilityQueueStore,
    request: CapabilityDispatchRequest,
) -> CapabilityDispatchResponse:
    record = queue.dispatch(request)
    return CapabilityDispatchResponse(
        request_id=record.request.request_id,
        status=CapabilityJobStatus.PENDING,
        queued_at=record.queued_at.isoformat(),
    )


def list_pending_capabilities_response(
    queue: CapabilityQueueStore,
    *,
    executor: str,
    limit: int,
) -> CapabilityPendingResponse:
    safe_limit = max(1, min(limit, 50))
    return CapabilityPendingResponse(items=queue.claim_pending(executor, limit=safe_limit))


def complete_capability_response(
    queue: CapabilityQueueStore,
    result: CapabilityResult,
) -> CapabilityCompleteResponse:
    record = queue.complete(result)
    if record is None:
        raise HTTPException(status_code=404, detail="capability request not found")
    return CapabilityCompleteResponse(
        request_id=result.request_id,
        status=record.status,
        completed_at=record.completed_at.isoformat() if record.completed_at else None,
    )


def get_capability_result_response(queue: CapabilityQueueStore, request_id: str) -> dict:
    snapshot = queue.get(request_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="capability request not found")
    return snapshot.model_dump(mode="json")


def get_capability_queue_status_response(queue: CapabilityQueueStore) -> CapabilityQueueStatusResponse:
    status = queue.status_counts()
    return CapabilityQueueStatusResponse(
        pending=status["pending"],
        pending_approval=status["pending_approval"],
        in_progress=status["in_progress"],
        completed=status["completed"],
        dead_letter=status["dead_letter"],
    )


def list_pending_approvals_response(
    queue: CapabilityQueueStore,
    *,
    limit: int,
) -> CapabilityApprovalPendingResponse:
    snapshots = queue.list_pending_approvals(limit=limit)
    return CapabilityApprovalPendingResponse(items=[_to_pending_item(snapshot) for snapshot in snapshots])


def list_approval_history_response(
    queue: CapabilityQueueStore,
    *,
    limit: int,
    action: CapabilityApprovalAction | None,
    approver: str | None,
    capability: str | None,
    request_id: str | None,
) -> CapabilityApprovalHistoryResponse:
    events = queue.list_approval_events(
        limit=limit,
        action=action,
        approver=approver,
        capability=capability,
        request_id=request_id,
    )
    return CapabilityApprovalHistoryResponse(
        items=[CapabilityApprovalHistoryItem.model_validate(event) for event in events],
    )


def approve_capability_response(
    queue: CapabilityQueueStore,
    *,
    request_id: str,
    approver: str | None,
) -> CapabilityApprovalDecisionResponse:
    record = queue.approve_request(request_id, approver=approver)
    return _to_decision_response(record, not_found_detail="capability approval request not found")


def reject_capability_response(
    queue: CapabilityQueueStore,
    *,
    request_id: str,
    approver: str | None,
    reason: str | None,
) -> CapabilityApprovalDecisionResponse:
    record = queue.reject_request(request_id, approver=approver, reason=reason)
    return _to_decision_response(record, not_found_detail="capability approval request not found")


def requeue_dead_letter_response(
    queue: CapabilityQueueStore,
    *,
    request_id: str,
) -> CapabilityDispatchResponse:
    record = queue.requeue_dead_letter(request_id)
    if record is None:
        raise HTTPException(status_code=404, detail="dead-letter capability request not found")
    return CapabilityDispatchResponse(
        request_id=record.request.request_id,
        status=record.status,
        queued_at=record.queued_at.isoformat(),
    )


def _to_pending_item(snapshot: CapabilityJobSnapshot) -> CapabilityApprovalPendingItem:
    return CapabilityApprovalPendingItem(
        request=snapshot.request,
        queued_at=snapshot.queued_at,
    )


def _to_decision_response(record, *, not_found_detail: str) -> CapabilityApprovalDecisionResponse:
    if record is None:
        raise HTTPException(status_code=404, detail=not_found_detail)
    return CapabilityApprovalDecisionResponse(
        request_id=record.request.request_id,
        status=record.status,
        approval_status=record.request.approval_status,
        completed_at=record.completed_at.isoformat() if record.completed_at else None,
    )
