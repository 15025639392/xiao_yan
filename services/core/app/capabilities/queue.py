from __future__ import annotations

from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Any, cast

from app.capabilities.models import (
    CAPABILITY_DESCRIPTORS,
    CapabilityApprovalAction,
    CapabilityApprovalStatus,
    CapabilityAudit,
    CapabilityDispatchRequest,
    CapabilityJobSnapshot,
    CapabilityJobStatus,
    CapabilityPendingItem,
    CapabilityRequest,
    CapabilityResult,
)
from app.capabilities.heartbeat_registry import CapabilityExecutorHeartbeatRegistry
from app.capabilities.queue_persistence import CapabilityQueuePersistence
from app.capabilities.queue_records import (
    CapabilityRecord,
    current_time,
    deserialize_capability_record,
    normalize_idempotency_key,
    now_iso,
    serialize_capability_record,
)
from app.capabilities.queue_mutations import (
    approve_record,
    reject_record,
    requeue_dead_letter,
)
from app.capabilities.queue_runtime import (
    ClaimPendingResult,
    apply_completion_result,
    build_dispatch_record,
    bump_attempt_or_dead_letter,
    claim_pending_items,
    mark_dead_letter_for_error,
)
from app.capabilities.queue_views import (
    append_approval_event,
    build_job_snapshot,
    compute_status_counts,
    filter_approval_events,
    list_job_snapshots,
    list_pending_approval_snapshots,
)
class CapabilityQueueStore:
    """Capability queue with light persistence/retry/dead-letter semantics."""

    def __init__(self, *, storage_path: Path | None = None) -> None:
        self._lock = Lock()
        self._persistence = CapabilityQueuePersistence(storage_path=storage_path)
        self._order: list[str] = []
        self._records: dict[str, CapabilityRecord] = {}
        self._idempotency_index: dict[str, str] = {}
        self._approval_events: list[dict[str, Any]] = []
        self._descriptor_by_name = {d.name: d for d in CAPABILITY_DESCRIPTORS}
        self._heartbeat_registry = CapabilityExecutorHeartbeatRegistry()
        self._load_from_disk()

    def _load_from_disk(self) -> None:
        state = self._persistence.load()
        loaded_records: dict[str, CapabilityRecord] = {}
        for request_id, raw_record in state.records.items():
            if not isinstance(request_id, str) or not isinstance(raw_record, dict):
                continue
            record = deserialize_capability_record(raw_record)
            if record is None:
                continue
            loaded_records[request_id] = record

        loaded_order: list[str] = []
        if state.order:
            seen: set[str] = set()
            for item in state.order:
                if item in loaded_records and item not in seen:
                    loaded_order.append(item)
                    seen.add(item)
            for request_id in loaded_records:
                if request_id not in seen:
                    loaded_order.append(request_id)
        else:
            loaded_order = list(loaded_records.keys())

        self._records = loaded_records
        self._order = loaded_order
        self._idempotency_index = {}
        self._approval_events = [dict(event) for event in state.approval_events]
        for request_id, record in self._records.items():
            key = normalize_idempotency_key(record.request.idempotency_key)
            if key:
                self._idempotency_index[key] = request_id

    def _persist_locked(self) -> None:
        self._persistence.persist(
            order=self._order,
            records={
                request_id: serialize_capability_record(record)
                for request_id, record in self._records.items()
            },
            approval_events=self._approval_events,
        )

    def reset(self) -> None:
        with self._lock:
            self._order.clear()
            self._records.clear()
            self._idempotency_index.clear()
            self._approval_events.clear()
            self._heartbeat_registry.clear()
            self._persist_locked()

    def dispatch(self, payload: CapabilityDispatchRequest) -> CapabilityRecord:
        descriptor = self._descriptor_by_name[payload.capability]
        risk_level = payload.risk_level or descriptor.default_risk_level
        requires_approval = (
            descriptor.default_requires_approval
            if payload.requires_approval is None
            else payload.requires_approval
        )
        idempotency_key = normalize_idempotency_key(payload.idempotency_key)

        with self._lock:
            if idempotency_key is not None:
                existing_id = self._idempotency_index.get(idempotency_key)
                if existing_id is not None:
                    existing = self._records.get(existing_id)
                    if existing is not None:
                        return existing

            payload = payload.model_copy(update={"idempotency_key": idempotency_key})
            record = build_dispatch_record(
                payload,
                request_id=None,
                risk_level=risk_level,
                requires_approval=requires_approval,
                queued_at=current_time(),
            )
            self._order.append(record.request.request_id)
            self._records[record.request.request_id] = record
            if idempotency_key is not None:
                self._idempotency_index[idempotency_key] = record.request.request_id
            self._persist_locked()
            return record

    def _mark_dead_letter_locked(
        self,
        record: CapabilityRecord,
        *,
        error_code: str,
        error_message: str,
    ) -> None:
        mark_dead_letter_for_error(
            record,
            finished_at=current_time(),
            error_code=error_code,
            error_message=error_message,
        )

    def _bump_attempt_locked(self, record: CapabilityRecord) -> bool:
        return bump_attempt_or_dead_letter(record, now=current_time())

    def claim_pending(self, executor: str, *, limit: int, lease_seconds: int = 30) -> list[CapabilityPendingItem]:
        # `executor` is reserved for future multi-executor routing.
        _ = executor
        now = current_time()

        with self._lock:
            claim_result: ClaimPendingResult = claim_pending_items(
                order=self._order,
                records=self._records,
                limit=limit,
                lease_seconds=lease_seconds,
                now=now,
            )
            if claim_result.mutated:
                self._persist_locked()

        return claim_result.items

    def complete(self, result: CapabilityResult) -> CapabilityRecord | None:
        now = current_time()
        with self._lock:
            record = self._records.get(result.request_id)
            if record is None:
                return None
            # Idempotency: once completed, keep the first completion result.
            if record.status == CapabilityJobStatus.COMPLETED:
                return record

            apply_completion_result(record=record, result=result, now=now)
            self._persist_locked()
            return record

    def list_pending_approvals(self, *, limit: int = 50) -> list[CapabilityJobSnapshot]:
        with self._lock:
            return list_pending_approval_snapshots(
                order=self._order,
                records=self._records,
                limit=limit,
            )

    def _append_approval_event_locked(
        self,
        *,
        request: CapabilityRequest,
        action: CapabilityApprovalAction,
        approver: str,
        reason: str | None,
        decided_at: str,
    ) -> None:
        self._approval_events = append_approval_event(
            self._approval_events,
            request=request,
            action=action,
            approver=approver,
            reason=reason,
            decided_at=decided_at,
        )

    def list_approval_events(
        self,
        *,
        limit: int = 50,
        action: CapabilityApprovalAction | None = None,
        approver: str | None = None,
        capability: str | None = None,
        request_id: str | None = None,
    ) -> list[dict[str, Any]]:
        with self._lock:
            return filter_approval_events(
                self._approval_events,
                limit=limit,
                action=action,
                approver=approver,
                capability=capability,
                request_id=request_id,
            )

    def approve_request(self, request_id: str, *, approver: str | None = None) -> CapabilityRecord | None:
        decided_by = (approver or "").strip() or "system"
        decided_at = now_iso()
        with self._lock:
            record = self._records.get(request_id)
            if record is None:
                return None
            if record.status != CapabilityJobStatus.PENDING:
                return None
            if not record.request.requires_approval:
                return None
            if record.request.approval_status != CapabilityApprovalStatus.PENDING:
                return None
            approve_record(record, approver=decided_by, decided_at=decided_at)
            self._append_approval_event_locked(
                request=record.request,
                action=CapabilityApprovalAction.APPROVED,
                approver=decided_by,
                reason=None,
                decided_at=decided_at,
            )
            self._persist_locked()
            return record

    def reject_request(
        self,
        request_id: str,
        *,
        approver: str | None = None,
        reason: str | None = None,
    ) -> CapabilityRecord | None:
        decided_by = (approver or "").strip() or "system"
        reason_text = (reason or "").strip() or "rejected by approver"
        finished = current_time()
        decided_at = finished.isoformat()
        with self._lock:
            record = self._records.get(request_id)
            if record is None:
                return None
            if record.status == CapabilityJobStatus.COMPLETED:
                return None
            if not record.request.requires_approval:
                return None
            if record.request.approval_status != CapabilityApprovalStatus.PENDING:
                return None

            reject_record(
                record,
                approver=decided_by,
                reason=reason_text,
                finished_at=finished,
                decided_at=decided_at,
            )
            self._append_approval_event_locked(
                request=record.request,
                action=CapabilityApprovalAction.REJECTED,
                approver=decided_by,
                reason=reason_text,
                decided_at=decided_at,
            )
            self._persist_locked()
            return record

    def requeue_dead_letter(self, request_id: str) -> CapabilityRecord | None:
        with self._lock:
            record = self._records.get(request_id)
            if record is None:
                return None
            if not record.dead_lettered:
                return None
            requeue_dead_letter(record)
            self._persist_locked()
            return record

    def get(self, request_id: str) -> CapabilityJobSnapshot | None:
        with self._lock:
            record = self._records.get(request_id)
            if record is None:
                return None
            return build_job_snapshot(record)

    def status_counts(self) -> dict[str, int]:
        with self._lock:
            return compute_status_counts(self._records.values())

    def list_snapshots(
        self,
        *,
        limit: int = 50,
        status: CapabilityJobStatus | None = None,
        dead_letter_only: bool = False,
    ) -> list[CapabilityJobSnapshot]:
        with self._lock:
            return list_job_snapshots(
                order=self._order,
                records=self._records,
                limit=limit,
                status=status,
                dead_letter_only=dead_letter_only,
            )

    def mark_executor_heartbeat(self, executor: str) -> str:
        now = current_time()
        with self._lock:
            self._heartbeat_registry.mark(executor, now=now)
        return now.isoformat()

    def has_recent_executor(self, executor: str, *, max_age_seconds: int = 10) -> bool:
        with self._lock:
            return self._heartbeat_registry.has_recent(
                executor,
                now=current_time(),
                max_age_seconds=max_age_seconds,
            )
