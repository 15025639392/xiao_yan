from __future__ import annotations

from datetime import datetime, timezone
import time

from app.capabilities.models import (
    CapabilityAudit,
    CapabilityDispatchRequest,
    CapabilityResult,
)
from app.capabilities.queue import CapabilityQueueStore
from app.capabilities.queue_records import CapabilityRecord
from app.config import get_capability_queue_storage_path

_capability_queue = CapabilityQueueStore(storage_path=get_capability_queue_storage_path())


def get_capability_queue() -> CapabilityQueueStore:
    return _capability_queue


def reset_capability_queue_for_tests() -> None:
    global _capability_queue
    _capability_queue = CapabilityQueueStore()


def dispatch_capability_request(payload: CapabilityDispatchRequest) -> CapabilityRecord:
    return _capability_queue.dispatch(payload)


def wait_for_capability_result(
    request_id: str,
    *,
    timeout_seconds: float = 1.0,
    poll_interval_seconds: float = 0.05,
) -> CapabilityResult | None:
    timeout = max(0.01, timeout_seconds)
    poll = max(0.01, poll_interval_seconds)
    deadline = time.monotonic() + timeout

    while time.monotonic() <= deadline:
        snapshot = _capability_queue.get(request_id)
        if snapshot is not None and snapshot.status.value == "completed" and snapshot.result is not None:
            return snapshot.result
        time.sleep(poll)

    return None


def dispatch_and_wait(
    payload: CapabilityDispatchRequest,
    *,
    timeout_seconds: float = 1.0,
    poll_interval_seconds: float = 0.05,
) -> CapabilityResult | None:
    record = dispatch_capability_request(payload)
    result = wait_for_capability_result(
        record.request.request_id,
        timeout_seconds=timeout_seconds,
        poll_interval_seconds=poll_interval_seconds,
    )
    if result is None:
        # Timeout fallback path is used by core; mark this request as completed
        # to avoid stale pending jobs being executed later by desktop workers.
        finished = datetime.now(timezone.utc)
        started = finished
        get_capability_queue().complete(
            CapabilityResult(
                request_id=record.request.request_id,
                ok=False,
                error_code="dispatch_timeout_fallback",
                error_message="capability dispatch timed out and core fallback was used",
                audit=CapabilityAudit(
                    executor="core",
                    started_at=started.isoformat(),
                    finished_at=finished.isoformat(),
                    duration_ms=0,
                ),
            )
        )
    return result


def mark_capability_executor_heartbeat(executor: str) -> str:
    return get_capability_queue().mark_executor_heartbeat(executor)


def has_recent_capability_executor(executor: str, *, max_age_seconds: int = 10) -> bool:
    return get_capability_queue().has_recent_executor(executor, max_age_seconds=max_age_seconds)
