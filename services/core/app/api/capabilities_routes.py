from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query

from app.capabilities.models import (
    CAPABILITY_DESCRIPTORS,
    CapabilityApprovalAction,
    CapabilityApprovalStatus,
    CapabilityApprovalDecisionRequest,
    CapabilityApprovalDecisionResponse,
    CapabilityApprovalHistoryItem,
    CapabilityApprovalHistoryResponse,
    CapabilityApprovalPendingItem,
    CapabilityApprovalPendingResponse,
    CapabilityJobAuditItem,
    CapabilityJobAuditResponse,
    CapabilityJobSnapshot,
    CapabilityName,
    CapabilityCompleteResponse,
    CapabilityDispatchRequest,
    CapabilityDispatchResponse,
    CapabilityJobStatus,
    CapabilityPendingResponse,
    CapabilityQueueStatusResponse,
    CapabilityRequest,
    CapabilityResult,
)
from app.capabilities.runtime import get_capability_queue, reset_capability_queue_for_tests
from app.capabilities.runtime import mark_capability_executor_heartbeat
from app.runtime_ext.runtime_config import get_runtime_config


def _reset_capability_queue_for_tests() -> None:
    reset_capability_queue_for_tests()


def build_capabilities_router() -> APIRouter:
    router = APIRouter()

    def _to_utc(value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

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

    @router.get("/capabilities/contract")
    def get_capability_contract() -> dict:
        return {
            "version": "v0",
            "descriptors": [d.model_dump(mode="json") for d in CAPABILITY_DESCRIPTORS],
            "request_schema": CapabilityRequest.model_json_schema(),
            "result_schema": CapabilityResult.model_json_schema(),
        }

    @router.post("/capabilities/dispatch")
    def dispatch_capability(request: CapabilityDispatchRequest) -> CapabilityDispatchResponse:
        queue = get_capability_queue()
        record = queue.dispatch(request)
        return CapabilityDispatchResponse(
            request_id=record.request.request_id,
            status=CapabilityJobStatus.PENDING,
            queued_at=record.queued_at.isoformat(),
        )

    @router.get("/capabilities/pending")
    def list_pending_capabilities(executor: str = "desktop", limit: int = 5) -> CapabilityPendingResponse:
        safe_limit = max(1, min(limit, 50))
        queue = get_capability_queue()
        items = queue.claim_pending(executor, limit=safe_limit)
        return CapabilityPendingResponse(items=items)

    @router.post("/capabilities/complete")
    def complete_capability(result: CapabilityResult) -> CapabilityCompleteResponse:
        queue = get_capability_queue()
        record = queue.complete(result)
        if record is None:
            raise HTTPException(status_code=404, detail="capability request not found")
        return CapabilityCompleteResponse(
            request_id=result.request_id,
            status=record.status,
            completed_at=record.completed_at.isoformat() if record.completed_at else None,
        )

    @router.get("/capabilities/result/{request_id}")
    def get_capability_result(request_id: str) -> dict:
        queue = get_capability_queue()
        snapshot = queue.get(request_id)
        if snapshot is None:
            raise HTTPException(status_code=404, detail="capability request not found")
        return snapshot.model_dump(mode="json")

    @router.get("/capabilities/queue/status")
    def get_capability_queue_status() -> CapabilityQueueStatusResponse:
        queue = get_capability_queue()
        status = queue.status_counts()
        return CapabilityQueueStatusResponse(
            pending=status["pending"],
            pending_approval=status["pending_approval"],
            in_progress=status["in_progress"],
            completed=status["completed"],
            dead_letter=status["dead_letter"],
        )

    @router.get("/capabilities/jobs")
    def list_capability_jobs(
        limit: int = Query(default=30, ge=1, le=200),
        status: CapabilityJobStatus | None = Query(default=None),
        dead_letter_only: bool = Query(default=False),
        approval_status: CapabilityApprovalStatus | None = Query(default=None),
        approver: str | None = Query(default=None),
        capability: CapabilityName | None = Query(default=None),
        request_id: str | None = Query(default=None),
        queued_from: datetime | None = Query(default=None),
        queued_to: datetime | None = Query(default=None),
        completed_from: datetime | None = Query(default=None),
        completed_to: datetime | None = Query(default=None),
        cursor: str | None = Query(default=None),
    ) -> CapabilityJobAuditResponse:
        cursor_offset = 0
        if cursor is not None:
            try:
                cursor_offset = int(cursor)
            except ValueError as error:
                raise HTTPException(status_code=400, detail="invalid cursor") from error
            if cursor_offset < 0:
                raise HTTPException(status_code=400, detail="invalid cursor")

        queued_from_utc = _to_utc(queued_from)
        queued_to_utc = _to_utc(queued_to)
        completed_from_utc = _to_utc(completed_from)
        completed_to_utc = _to_utc(completed_to)

        queue = get_capability_queue()
        snapshots = queue.list_snapshots(limit=5000, status=status, dead_letter_only=dead_letter_only)
        filtered: list[CapabilityJobAuditItem] = []
        approver_filter = (approver or "").strip()
        request_id_filter = (request_id or "").strip()
        for snapshot in snapshots:
            if capability is not None and snapshot.request.capability != capability:
                continue
            if request_id_filter and snapshot.request.request_id != request_id_filter:
                continue
            if approval_status is not None and snapshot.request.approval_status != approval_status:
                continue
            if approver_filter:
                actor = snapshot.request.approved_by or snapshot.request.rejected_by or ""
                if actor != approver_filter:
                    continue

            queued_at = _parse_snapshot_time(snapshot.queued_at)
            if queued_from_utc is not None and (queued_at is None or queued_at < queued_from_utc):
                continue
            if queued_to_utc is not None and (queued_at is None or queued_at > queued_to_utc):
                continue

            completed_at = _parse_snapshot_time(snapshot.completed_at)
            if completed_from_utc is not None and (completed_at is None or completed_at < completed_from_utc):
                continue
            if completed_to_utc is not None and (completed_at is None or completed_at > completed_to_utc):
                continue

            policy_version, policy_revision = _extract_policy_metadata(snapshot)
            result = snapshot.result
            filtered.append(
                CapabilityJobAuditItem(
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
            )

        page = filtered[cursor_offset : cursor_offset + limit]
        next_cursor = None
        if cursor_offset + limit < len(filtered):
            next_cursor = str(cursor_offset + limit)
        return CapabilityJobAuditResponse(items=page, next_cursor=next_cursor)

    @router.get("/capabilities/approvals/pending")
    def list_capability_pending_approvals(
        limit: int = Query(default=30, ge=1, le=200),
    ) -> CapabilityApprovalPendingResponse:
        queue = get_capability_queue()
        snapshots = queue.list_pending_approvals(limit=limit)
        return CapabilityApprovalPendingResponse(
            items=[
                CapabilityApprovalPendingItem(
                    request=snapshot.request,
                    queued_at=snapshot.queued_at,
                )
                for snapshot in snapshots
            ]
        )

    @router.get("/capabilities/approvals/history")
    def list_capability_approval_history(
        limit: int = Query(default=30, ge=1, le=200),
        action: CapabilityApprovalAction | None = Query(default=None),
        approver: str | None = Query(default=None),
        capability: CapabilityName | None = Query(default=None),
        request_id: str | None = Query(default=None),
    ) -> CapabilityApprovalHistoryResponse:
        queue = get_capability_queue()
        events = queue.list_approval_events(
            limit=limit,
            action=action,
            approver=approver,
            capability=capability.value if capability is not None else None,
            request_id=request_id,
        )
        return CapabilityApprovalHistoryResponse(
            items=[CapabilityApprovalHistoryItem.model_validate(event) for event in events],
        )

    @router.post("/capabilities/approvals/{request_id}/approve")
    def approve_capability_request(
        request_id: str,
        request: CapabilityApprovalDecisionRequest,
    ) -> CapabilityApprovalDecisionResponse:
        queue = get_capability_queue()
        record = queue.approve_request(request_id, approver=request.approver)
        if record is None:
            raise HTTPException(status_code=404, detail="capability approval request not found")
        return CapabilityApprovalDecisionResponse(
            request_id=record.request.request_id,
            status=record.status,
            approval_status=record.request.approval_status,
            completed_at=record.completed_at.isoformat() if record.completed_at else None,
        )

    @router.post("/capabilities/approvals/{request_id}/reject")
    def reject_capability_request(
        request_id: str,
        request: CapabilityApprovalDecisionRequest,
    ) -> CapabilityApprovalDecisionResponse:
        queue = get_capability_queue()
        record = queue.reject_request(request_id, approver=request.approver, reason=request.reason)
        if record is None:
            raise HTTPException(status_code=404, detail="capability approval request not found")
        return CapabilityApprovalDecisionResponse(
            request_id=record.request.request_id,
            status=record.status,
            approval_status=record.request.approval_status,
            completed_at=record.completed_at.isoformat() if record.completed_at else None,
        )

    @router.post("/capabilities/dead-letter/requeue/{request_id}")
    def requeue_dead_letter_capability(request_id: str) -> CapabilityDispatchResponse:
        queue = get_capability_queue()
        record = queue.requeue_dead_letter(request_id)
        if record is None:
            raise HTTPException(status_code=404, detail="dead-letter capability request not found")
        return CapabilityDispatchResponse(
            request_id=record.request.request_id,
            status=record.status,
            queued_at=record.queued_at.isoformat(),
        )

    @router.post("/capabilities/heartbeat")
    def capability_executor_heartbeat(executor: str = "desktop") -> dict:
        heartbeat_at = mark_capability_executor_heartbeat(executor)
        return {"executor": executor, "heartbeat_at": heartbeat_at}

    @router.get("/capabilities/shell-policy")
    def get_capability_shell_policy() -> dict:
        return get_runtime_config().get_capability_shell_policy()

    @router.get("/capabilities/file-policy")
    def get_capability_file_policy() -> dict:
        return get_runtime_config().get_capability_file_policy()

    return router
