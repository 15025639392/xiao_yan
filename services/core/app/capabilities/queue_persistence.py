from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.capabilities.models import CapabilityJobStatus, CapabilityRequest, CapabilityResult
from app.utils.file_utils import read_json_file, write_json_file

CAPABILITY_QUEUE_PERSIST_VERSION = "v1"


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def isoformat_or_none(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except Exception:
        return None


@dataclass
class CapabilityQueuePersistedState:
    order: list[str]
    records: dict[str, dict[str, Any]]
    approval_events: list[dict[str, Any]]


class CapabilityQueuePersistence:
    def __init__(self, *, storage_path: Path | None = None) -> None:
        self._storage_path = storage_path

    def load(self) -> CapabilityQueuePersistedState:
        if self._storage_path is None or not self._storage_path.exists():
            return CapabilityQueuePersistedState(order=[], records={}, approval_events=[])
        try:
            payload = read_json_file(self._storage_path)
        except Exception:
            return CapabilityQueuePersistedState(order=[], records={}, approval_events=[])
        if not isinstance(payload, dict):
            return CapabilityQueuePersistedState(order=[], records={}, approval_events=[])

        raw_records = payload.get("records")
        records = raw_records if isinstance(raw_records, dict) else {}

        raw_order = payload.get("order")
        order: list[str] = []
        if isinstance(raw_order, list):
            for item in raw_order:
                if isinstance(item, str):
                    order.append(item)

        approval_events: list[dict[str, Any]] = []
        raw_events = payload.get("approval_events")
        if isinstance(raw_events, list):
            for event in raw_events:
                if isinstance(event, dict):
                    approval_events.append(dict(event))

        return CapabilityQueuePersistedState(
            order=order,
            records=records,
            approval_events=approval_events,
        )

    def persist(
        self,
        *,
        order: list[str],
        records: dict[str, Any],
        approval_events: list[dict[str, Any]],
    ) -> None:
        if self._storage_path is None:
            return
        payload = {
            "version": CAPABILITY_QUEUE_PERSIST_VERSION,
            "saved_at": now_utc().isoformat(),
            "order": list(order),
            "records": records,
            "approval_events": [dict(event) for event in approval_events],
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
            return


def serialize_record(
    *,
    request: CapabilityRequest,
    status: CapabilityJobStatus,
    queued_at: datetime,
    lease_expires_at: datetime | None,
    completed_at: datetime | None,
    result: CapabilityResult | None,
    dead_lettered: bool,
    last_error_code: str | None,
    last_error_message: str | None,
) -> dict[str, Any]:
    return {
        "request": request.model_dump(mode="json"),
        "status": status.value,
        "queued_at": queued_at.isoformat(),
        "lease_expires_at": isoformat_or_none(lease_expires_at),
        "completed_at": isoformat_or_none(completed_at),
        "result": result.model_dump(mode="json") if result else None,
        "dead_lettered": bool(dead_lettered),
        "last_error_code": last_error_code,
        "last_error_message": last_error_message,
    }


def deserialize_record(payload: dict[str, Any]) -> dict[str, Any] | None:
    try:
        request = CapabilityRequest.model_validate(payload.get("request", {}))
        status = CapabilityJobStatus(payload.get("status", CapabilityJobStatus.PENDING.value))
        queued_at = parse_iso(payload.get("queued_at")) or now_utc()
        lease_expires_at = parse_iso(payload.get("lease_expires_at"))
        completed_at = parse_iso(payload.get("completed_at"))
        raw_result = payload.get("result")
        result = CapabilityResult.model_validate(raw_result) if isinstance(raw_result, dict) else None
        dead_lettered = bool(payload.get("dead_lettered", False))
        last_error_code = payload.get("last_error_code")
        last_error_message = payload.get("last_error_message")
        return {
            "request": request,
            "status": status,
            "queued_at": queued_at,
            "lease_expires_at": lease_expires_at,
            "completed_at": completed_at,
            "result": result,
            "dead_lettered": dead_lettered,
            "last_error_code": last_error_code if isinstance(last_error_code, str) else None,
            "last_error_message": last_error_message if isinstance(last_error_message, str) else None,
        }
    except Exception:
        return None
