from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
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
from app.utils.file_utils import read_json_file, write_json_file

DEFAULT_MAX_ATTEMPTS = 3
MAX_ATTEMPTS_HARD_LIMIT = 20
CAPABILITY_QUEUE_PERSIST_VERSION = "v1"

_RETRYABLE_ERROR_CODES: set[str] = {
    "execution_error",
    "timeout",
    "executor_unavailable",
    "lease_expired",
}



def _now() -> datetime:
    return datetime.now(timezone.utc)



def _iso(dt: datetime) -> str:
    return dt.isoformat()



def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except Exception:
        return None



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
        self._storage_path = storage_path
        self._order: list[str] = []
        self._records: dict[str, _CapabilityRecord] = {}
        self._idempotency_index: dict[str, str] = {}
        self._approval_events: list[dict[str, Any]] = []
        self._descriptor_by_name = {d.name: d for d in CAPABILITY_DESCRIPTORS}
        self._executor_heartbeats: dict[str, datetime] = {}
        self._load_from_disk()

    def _serialize_record(self, record: _CapabilityRecord) -> dict[str, Any]:
        return {
            "request": record.request.model_dump(mode="json"),
            "status": record.status.value,
            "queued_at": _iso(record.queued_at),
            "lease_expires_at": _iso(record.lease_expires_at) if record.lease_expires_at else None,
            "completed_at": _iso(record.completed_at) if record.completed_at else None,
            "result": record.result.model_dump(mode="json") if record.result else None,
            "dead_lettered": bool(record.dead_lettered),
            "last_error_code": record.last_error_code,
            "last_error_message": record.last_error_message,
        }

    def _deserialize_record(self, payload: dict[str, Any]) -> _CapabilityRecord | None:
        try:
            request = CapabilityRequest.model_validate(payload.get("request", {}))
            status = CapabilityJobStatus(payload.get("status", CapabilityJobStatus.PENDING.value))
            queued_at = _parse_iso(payload.get("queued_at")) or _now()
            lease_expires_at = _parse_iso(payload.get("lease_expires_at"))
            completed_at = _parse_iso(payload.get("completed_at"))
            raw_result = payload.get("result")
            result = CapabilityResult.model_validate(raw_result) if isinstance(raw_result, dict) else None
            dead_lettered = bool(payload.get("dead_lettered", False))
            last_error_code = payload.get("last_error_code")
            last_error_message = payload.get("last_error_message")
            return _CapabilityRecord(
                request=request,
                status=status,
                queued_at=queued_at,
                lease_expires_at=lease_expires_at,
                completed_at=completed_at,
                result=result,
                dead_lettered=dead_lettered,
                last_error_code=last_error_code if isinstance(last_error_code, str) else None,
                last_error_message=last_error_message if isinstance(last_error_message, str) else None,
            )
        except Exception:
            return None

    def _load_from_disk(self) -> None:
        if self._storage_path is None or not self._storage_path.exists():
            return
        try:
            payload = read_json_file(self._storage_path)
        except Exception:
            return
        if not isinstance(payload, dict):
            return

        records_payload = payload.get("records")
        if not isinstance(records_payload, dict):
            return

        loaded_records: dict[str, _CapabilityRecord] = {}
        for request_id, raw_record in records_payload.items():
            if not isinstance(request_id, str) or not isinstance(raw_record, dict):
                continue
            record = self._deserialize_record(raw_record)
            if record is None:
                continue
            loaded_records[request_id] = record

        order = payload.get("order")
        loaded_order: list[str] = []
        if isinstance(order, list):
            seen: set[str] = set()
            for item in order:
                if isinstance(item, str) and item in loaded_records and item not in seen:
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
        raw_events = payload.get("approval_events")
        self._approval_events = []
        if isinstance(raw_events, list):
            for event in raw_events:
                if isinstance(event, dict):
                    self._approval_events.append(dict(event))
        for request_id, record in self._records.items():
            key = _normalize_idempotency_key(record.request.idempotency_key)
            if key:
                self._idempotency_index[key] = request_id

    def _persist_locked(self) -> None:
        if self._storage_path is None:
            return
        payload = {
            "version": CAPABILITY_QUEUE_PERSIST_VERSION,
            "saved_at": _iso(_now()),
            "order": list(self._order),
            "records": {
                request_id: self._serialize_record(record)
                for request_id, record in self._records.items()
            },
            "idempotency_index": dict(self._idempotency_index),
            "approval_events": [dict(event) for event in self._approval_events],
        }
        try:
            write_json_file(
                self._storage_path,
                payload,
                ensure_ascii=False,
                indent=2,
                create_parent=True,
            )
        except Exception:
            # persistence failure should not crash runtime capability flows
            return

    def reset(self) -> None:
        with self._lock:
            self._order.clear()
            self._records.clear()
            self._idempotency_index.clear()
            self._approval_events.clear()
            self._executor_heartbeats.clear()
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
        finished = _now()
        record.status = CapabilityJobStatus.COMPLETED
        record.lease_expires_at = None
        record.completed_at = finished
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
                started_at=finished.isoformat(),
                finished_at=finished.isoformat(),
                duration_ms=0,
            ),
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
        record.request = record.request.model_copy(
            update={"attempt": int(record.request.attempt) + 1},
            deep=True,
        )
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
                    record.request = record.request.model_copy(
                        update={"attempt": int(record.request.attempt) + 1},
                        deep=True,
                    )
                    record.status = CapabilityJobStatus.PENDING
                    record.lease_expires_at = None
                    record.completed_at = None
                    record.result = None
                    record.dead_lettered = False
                self._persist_locked()
                return record

            record.result = result
            record.status = CapabilityJobStatus.COMPLETED
            record.completed_at = now
            record.lease_expires_at = None
            record.dead_lettered = False
            record.last_error_code = result.error_code
            record.last_error_message = result.error_message
            self._persist_locked()
            return record

    def list_pending_approvals(self, *, limit: int = 50) -> list[CapabilityJobSnapshot]:
        requested = max(1, min(int(limit), 500))
        snapshots: list[CapabilityJobSnapshot] = []
        with self._lock:
            for request_id in reversed(self._order):
                if len(snapshots) >= requested:
                    break
                record = self._records.get(request_id)
                if record is None:
                    continue
                if record.status != CapabilityJobStatus.PENDING:
                    continue
                if record.request.approval_status != CapabilityApprovalStatus.PENDING:
                    continue
                snapshots.append(
                    CapabilityJobSnapshot(
                        request=record.request,
                        status=record.status,
                        queued_at=_iso(record.queued_at),
                        completed_at=_iso(record.completed_at) if record.completed_at else None,
                        result=record.result,
                    )
                )
        return snapshots

    def _append_approval_event_locked(
        self,
        *,
        request: CapabilityRequest,
        action: CapabilityApprovalAction,
        approver: str,
        reason: str | None,
        decided_at: str,
    ) -> None:
        event: dict[str, Any] = {
            "request_id": request.request_id,
            "capability": request.capability.value,
            "action": action.value,
            "approver": approver,
            "reason": reason,
            "decided_at": decided_at,
        }
        self._approval_events.append(event)
        if len(self._approval_events) > 2000:
            self._approval_events = self._approval_events[-2000:]

    def list_approval_events(
        self,
        *,
        limit: int = 50,
        action: CapabilityApprovalAction | None = None,
        approver: str | None = None,
        capability: str | None = None,
        request_id: str | None = None,
    ) -> list[dict[str, Any]]:
        requested = max(1, min(int(limit), 500))
        approver_filter = (approver or "").strip()
        capability_filter = (capability or "").strip()
        request_id_filter = (request_id or "").strip()

        results: list[dict[str, Any]] = []
        with self._lock:
            for event in reversed(self._approval_events):
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
            record.request = record.request.model_copy(
                update={
                    "approval_status": CapabilityApprovalStatus.APPROVED,
                    "approved_by": decided_by,
                    "approved_at": decided_at,
                },
                deep=True,
            )
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

            record.request = record.request.model_copy(
                update={
                    "approval_status": CapabilityApprovalStatus.REJECTED,
                    "rejected_by": decided_by,
                    "rejected_at": decided_at,
                    "rejection_reason": reason_text,
                },
                deep=True,
            )
            self._append_approval_event_locked(
                request=record.request,
                action=CapabilityApprovalAction.REJECTED,
                approver=decided_by,
                reason=reason_text,
                decided_at=decided_at,
            )
            record.status = CapabilityJobStatus.COMPLETED
            record.lease_expires_at = None
            record.completed_at = finished
            record.dead_lettered = False
            record.last_error_code = "approval_rejected"
            record.last_error_message = reason_text
            record.result = CapabilityResult(
                request_id=record.request.request_id,
                ok=False,
                error_code="approval_rejected",
                error_message=reason_text,
                audit=CapabilityAudit(
                    executor="core",
                    started_at=finished.isoformat(),
                    finished_at=finished.isoformat(),
                    duration_ms=0,
                ),
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
            record.status = CapabilityJobStatus.PENDING
            record.lease_expires_at = None
            record.completed_at = None
            record.result = None
            record.dead_lettered = False
            record.last_error_code = None
            record.last_error_message = None
            record.request = record.request.model_copy(update={"attempt": 1}, deep=True)
            self._persist_locked()
            return record

    def get(self, request_id: str) -> CapabilityJobSnapshot | None:
        with self._lock:
            record = self._records.get(request_id)
            if record is None:
                return None
            return CapabilityJobSnapshot(
                request=record.request,
                status=record.status,
                queued_at=_iso(record.queued_at),
                completed_at=_iso(record.completed_at) if record.completed_at else None,
                result=record.result,
            )

    def status_counts(self) -> dict[str, int]:
        with self._lock:
            pending = 0
            pending_approval = 0
            in_progress = 0
            completed = 0
            dead_letter = 0
            for record in self._records.values():
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

    def list_snapshots(
        self,
        *,
        limit: int = 50,
        status: CapabilityJobStatus | None = None,
        dead_letter_only: bool = False,
    ) -> list[CapabilityJobSnapshot]:
        requested = max(1, min(int(limit), 5000))
        snapshots: list[CapabilityJobSnapshot] = []
        with self._lock:
            for request_id in reversed(self._order):
                if len(snapshots) >= requested:
                    break
                record = self._records.get(request_id)
                if record is None:
                    continue
                if status is not None and record.status != status:
                    continue
                if dead_letter_only and not record.dead_lettered:
                    continue
                snapshots.append(
                    CapabilityJobSnapshot(
                        request=record.request,
                        status=record.status,
                        queued_at=_iso(record.queued_at),
                        completed_at=_iso(record.completed_at) if record.completed_at else None,
                        result=record.result,
                    )
                )
        return snapshots

    def mark_executor_heartbeat(self, executor: str) -> str:
        now = _now()
        with self._lock:
            self._executor_heartbeats[executor] = now
        return _iso(now)

    def has_recent_executor(self, executor: str, *, max_age_seconds: int = 10) -> bool:
        with self._lock:
            heartbeat = self._executor_heartbeats.get(executor)
        if heartbeat is None:
            return False
        age = (_now() - heartbeat).total_seconds()
        return age <= max(1, max_age_seconds)
