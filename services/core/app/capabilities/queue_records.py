from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, cast

from app.capabilities.models import CapabilityJobStatus, CapabilityRequest, CapabilityResult
from app.capabilities.queue_persistence import deserialize_record, now_utc, serialize_record


def current_time() -> datetime:
    return now_utc()


def now_iso() -> str:
    return current_time().isoformat()


def normalize_idempotency_key(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized if normalized else None


@dataclass
class CapabilityRecord:
    request: CapabilityRequest
    status: CapabilityJobStatus
    queued_at: datetime
    lease_expires_at: datetime | None = None
    completed_at: datetime | None = None
    result: CapabilityResult | None = None
    dead_lettered: bool = False
    last_error_code: str | None = None
    last_error_message: str | None = None


def serialize_capability_record(record: CapabilityRecord) -> dict[str, Any]:
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


def deserialize_capability_record(payload: dict[str, Any]) -> CapabilityRecord | None:
    loaded = deserialize_record(payload)
    if loaded is None:
        return None
    return CapabilityRecord(
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
