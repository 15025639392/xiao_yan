from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from threading import Lock
from typing import Any, cast
from uuid import uuid4

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
from app.capabilities.queue_persistence import (
    CapabilityQueuePersistence,
    deserialize_record,
    now_utc,
    serialize_record,
)
from app.capabilities.queue_mutations import (
    approve_record,
    bump_attempt,
    complete_success,
    mark_dead_letter,
    reject_record,
    requeue_dead_letter,
    reset_for_retry,
)
from app.capabilities.queue_views import (
    append_approval_event,
    build_job_snapshot,
    compute_status_counts,
    filter_approval_events,
    list_job_snapshots,
    list_pending_approval_snapshots,
)

DEFAULT_MAX_ATTEMPTS = 3
MAX_ATTEMPTS_HARD_LIMIT = 20

_RETRYABLE_ERROR_CODES: set[str] = {
    "execution_error",
    "timeout",
    "executor_unavailable",
    "lease_expired",
}



def _now() -> datetime:
    return now_utc()



def _iso(dt: datetime) -> str:
    return dt.isoformat()



def _normalize_idempotency_key(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized if normalized else None


@dataclass
class _CapabilityRecord:
    request: CapabilityRequest
    status: CapabilityJobStatus
    queued_at: datetime
    lease_expires_at: datetime | None = None
    completed_at: datetime | None = None
    result: CapabilityResult | None = None
    dead_lettered: bool = False
    last_error_code: str | None = None
    last_error_message: str | None = None


class CapabilityQueueStore:
    """Capability queue with light persistence/retry/dead-letter semantics."""

    def __init__(self, *, storage_path: Path | None = None) -> None:
        self._lock = Lock()
        self._persistence = CapabilityQueuePersistence(storage_path=storage_path)
        self._order: list[str] = []
        self._records: dict[str, _CapabilityRecord] = {}
        self._idempotency_index: dict[str, str] = {}
        self._approval_events: list[dict[str, Any]] = []
        self._descriptor_by_name = {d.name: d for d in CAPABILITY_DESCRIPTORS}
        self._heartbeat_registry = CapabilityExecutorHeartbeatRegistry()
        self._load_from_disk()

    def _serialize_record(self, record: _CapabilityRecord) -> dict[str, Any]:
        return serialize_record(
            request=record.request,
            status=record.status,
            queued_at=record.queued_at,
            lease_expires_at=record.lease_expires_at,
            completed_at=record.completed_at,
            result=record.result,
            dead_lettered=record.dead_lettered,
            last_error_code=record.last_error_code,
            last_error_message=record.last_error_message,
        )

    def _deserialize_record(self, payload: dict[str, Any]) -> _CapabilityRecord | None:
        loaded = deserialize_record(payload)
        if loaded is None:
            return None
        return _CapabilityRecord(
            request=cast(CapabilityRequest, loaded["request"]),
            status=cast(CapabilityJobStatus, loaded["status"]),
            queued_at=cast(datetime, loaded["queued_at"]),
            lease_expires_at=cast(datetime | None, loaded["lease_expires_at"]),
            completed_at=cast(datetime | None, loaded["completed_at"]),
            result=cast(CapabilityResult | None, loaded["result"]),
            dead_lettered=bool(loaded["dead_lettered"]),
            last_error_code=cast(str | None, loaded["last_error_code"]),
            last_error_message=cast(str | None, loaded["last_error_message"]),
        )

    def _load_from_disk(self) -> None:
        state = self._persistence.load()
        loaded_records: dict[str, _CapabilityRecord] = {}
        for request_id, raw_record in state.records.items():
            if not isinstance(request_id, str) or not isinstance(raw_record, dict):
                continue
            record = self._deserialize_record(raw_record)
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
            key = _normalize_idempotency_key(record.request.idempotency_key)
            if key:
                self._idempotency_index[key] = request_id

    def _persist_locked(self) -> None:
        self._persistence.persist(
            order=self._order,
            records={
                request_id: self._serialize_record(record)
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

    def dispatch(self, payload: CapabilityDispatchRequest) -> _CapabilityRecord:
        descriptor = self._descriptor_by_name[payload.capability]
        risk_level = payload.risk_level or descriptor.default_risk_level
        requires_approval = (
            descriptor.default_requires_approval
            if payload.requires_approval is None
            else payload.requires_approval
        )
        idempotency_key = _normalize_idempotency_key(payload.idempotency_key)

        with self._lock:
            if idempotency_key is not None:
                existing_id = self._idempotency_index.get(idempotency_key)
                if existing_id is not None:
                    existing = self._records.get(existing_id)
                    if existing is not None:
                        return existing

            request = CapabilityRequest(
                request_id=uuid4().hex,
                capability=payload.capability,
                args=payload.args,
                risk_level=risk_level,
                requires_approval=requires_approval,
                approval_status=(
                    CapabilityApprovalStatus.PENDING
                    if requires_approval
                    else CapabilityApprovalStatus.NOT_REQUIRED
                ),
                idempotency_key=idempotency_key,
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
            record = _CapabilityRecord(
                request=request,
                status=CapabilityJobStatus.PENDING,
                queued_at=_now(),
            )
            self._order.append(request.request_id)
            self._records[request.request_id] = record
            if idempotency_key is not None:
                self._idempotency_index[idempotency_key] = request.request_id
            self._persist_locked()
            return record

    def _mark_dead_letter_locked(
        self,
        record: _CapabilityRecord,
        *,
        error_code: str,
        error_message: str,
    ) -> None:
        mark_dead_letter(
            record,
            finished_at=_now(),
            error_code=error_code,
            error_message=error_message,
        )

    def _bump_attempt_locked(self, record: _CapabilityRecord) -> bool:
        if record.request.attempt >= record.request.max_attempts:
            self._mark_dead_letter_locked(
                record,
                error_code="dead_letter_exhausted_retries",
                error_message=(
                    f"retry limit reached ({record.request.attempt}/{record.request.max_attempts})"
                ),
            )
            return False
        bump_attempt(record)
        return True

    def claim_pending(self, executor: str, *, limit: int, lease_seconds: int = 30) -> list[CapabilityPendingItem]:
        # `executor` is reserved for future multi-executor routing.
        _ = executor
        now = _now()
        claimed: list[CapabilityPendingItem] = []
        lease_delta = timedelta(seconds=max(5, lease_seconds))
        mutated = False

        with self._lock:
            for request_id in self._order:
                if len(claimed) >= limit:
                    break
                record = self._records.get(request_id)
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
                    # lease expired: treat as retry attempt
                    if not self._bump_attempt_locked(record):
                        mutated = True
                        continue

                record.status = CapabilityJobStatus.IN_PROGRESS
                record.lease_expires_at = now + lease_delta
                record.dead_lettered = False
                mutated = True
                claimed.append(
                    CapabilityPendingItem(
                        request=record.request,
                        queued_at=_iso(record.queued_at),
                        lease_expires_at=_iso(cast(datetime, record.lease_expires_at)),
                    )
                )

            if mutated:
                self._persist_locked()

        return claimed

    def _is_retryable_failure(self, result: CapabilityResult) -> bool:
        if result.ok:
            return False
        code = (result.error_code or "").strip().lower()
        return code in _RETRYABLE_ERROR_CODES

    def complete(self, result: CapabilityResult) -> _CapabilityRecord | None:
        now = _now()
        with self._lock:
            record = self._records.get(result.request_id)
            if record is None:
                return None
            # Idempotency: once completed, keep the first completion result.
            if record.status == CapabilityJobStatus.COMPLETED:
                return record

            if self._is_retryable_failure(result):
                record.last_error_code = result.error_code
                record.last_error_message = result.error_message
                if record.request.attempt >= record.request.max_attempts:
                    message = result.error_message or "retry limit reached"
                    self._mark_dead_letter_locked(
                        record,
                        error_code="dead_letter_exhausted_retries",
                        error_message=message,
                    )
                else:
                    reset_for_retry(record, result=result)
                self._persist_locked()
                return record

            complete_success(record, result=result, completed_at=now)
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

    def approve_request(self, request_id: str, *, approver: str | None = None) -> _CapabilityRecord | None:
        decided_by = (approver or "").strip() or "system"
        decided_at = _iso(_now())
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
    ) -> _CapabilityRecord | None:
        decided_by = (approver or "").strip() or "system"
        reason_text = (reason or "").strip() or "rejected by approver"
        finished = _now()
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

    def requeue_dead_letter(self, request_id: str) -> _CapabilityRecord | None:
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
        now = _now()
        with self._lock:
            self._heartbeat_registry.mark(executor, now=now)
        return _iso(now)

    def has_recent_executor(self, executor: str, *, max_age_seconds: int = 10) -> bool:
        with self._lock:
            return self._heartbeat_registry.has_recent(
                executor,
                now=_now(),
                max_age_seconds=max_age_seconds,
            )
