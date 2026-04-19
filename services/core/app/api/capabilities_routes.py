from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Query

from app.api.capability_audit import build_job_audit_response
from app.api.capability_route_handlers import (
    approve_capability_response,
    complete_capability_response,
    dispatch_capability_response,
    get_capability_queue_status_response,
    get_capability_result_response,
    list_approval_history_response,
    list_pending_approvals_response,
    list_pending_capabilities_response,
    reject_capability_response,
    requeue_dead_letter_response,
)

from app.capabilities.models import (
    CAPABILITY_DESCRIPTORS,
    CapabilityApprovalAction,
    CapabilityApprovalStatus,
    CapabilityApprovalDecisionRequest,
    CapabilityApprovalDecisionResponse,
    CapabilityApprovalHistoryResponse,
    CapabilityApprovalPendingResponse,
    CapabilityJobAuditResponse,
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
        return dispatch_capability_response(queue, request)

    @router.get("/capabilities/pending")
    def list_pending_capabilities(executor: str = "desktop", limit: int = 5) -> CapabilityPendingResponse:
        queue = get_capability_queue()
        return list_pending_capabilities_response(queue, executor=executor, limit=limit)

    @router.post("/capabilities/complete")
    def complete_capability(result: CapabilityResult) -> CapabilityCompleteResponse:
        queue = get_capability_queue()
        return complete_capability_response(queue, result)

    @router.get("/capabilities/result/{request_id}")
    def get_capability_result(request_id: str) -> dict:
        queue = get_capability_queue()
        return get_capability_result_response(queue, request_id)

    @router.get("/capabilities/queue/status")
    def get_capability_queue_status() -> CapabilityQueueStatusResponse:
        queue = get_capability_queue()
        return get_capability_queue_status_response(queue)

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
        queue = get_capability_queue()
        return build_job_audit_response(
            queue=queue,
            limit=limit,
            status=status,
            dead_letter_only=dead_letter_only,
            approval_status=approval_status,
            approver=approver,
            capability=capability,
            request_id=request_id,
            queued_from=queued_from,
            queued_to=queued_to,
            completed_from=completed_from,
            completed_to=completed_to,
            cursor=cursor,
        )

    @router.get("/capabilities/approvals/pending")
    def list_capability_pending_approvals(
        limit: int = Query(default=30, ge=1, le=200),
    ) -> CapabilityApprovalPendingResponse:
        queue = get_capability_queue()
        return list_pending_approvals_response(queue, limit=limit)

    @router.get("/capabilities/approvals/history")
    def list_capability_approval_history(
        limit: int = Query(default=30, ge=1, le=200),
        action: CapabilityApprovalAction | None = Query(default=None),
        approver: str | None = Query(default=None),
        capability: CapabilityName | None = Query(default=None),
        request_id: str | None = Query(default=None),
    ) -> CapabilityApprovalHistoryResponse:
        queue = get_capability_queue()
        return list_approval_history_response(
            queue,
            limit=limit,
            action=action,
            approver=approver,
            capability=capability.value if capability is not None else None,
            request_id=request_id,
        )

    @router.post("/capabilities/approvals/{request_id}/approve")
    def approve_capability_request(
        request_id: str,
        request: CapabilityApprovalDecisionRequest,
    ) -> CapabilityApprovalDecisionResponse:
        queue = get_capability_queue()
        return approve_capability_response(queue, request_id=request_id, approver=request.approver)

    @router.post("/capabilities/approvals/{request_id}/reject")
    def reject_capability_request(
        request_id: str,
        request: CapabilityApprovalDecisionRequest,
    ) -> CapabilityApprovalDecisionResponse:
        queue = get_capability_queue()
        return reject_capability_response(
            queue,
            request_id=request_id,
            approver=request.approver,
            reason=request.reason,
        )

    @router.post("/capabilities/dead-letter/requeue/{request_id}")
    def requeue_dead_letter_capability(request_id: str) -> CapabilityDispatchResponse:
        queue = get_capability_queue()
        return requeue_dead_letter_response(queue, request_id=request_id)

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
