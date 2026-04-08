from app.capabilities.models import CapabilityAudit, CapabilityDispatchRequest, CapabilityResult
from app.capabilities.queue import CapabilityQueueStore


def test_capability_queue_persists_and_recovers_records(tmp_path):
    storage = tmp_path / "capability-queue.json"

    first = CapabilityQueueStore(storage_path=storage)
    record = first.dispatch(
        CapabilityDispatchRequest(
            capability="fs.read",
            args={"path": "README.md"},
            idempotency_key="persist-key",
        )
    )
    request_id = record.request.request_id

    claimed = first.claim_pending("desktop", limit=1)
    assert len(claimed) == 1
    assert claimed[0].request.request_id == request_id

    first.complete(
        CapabilityResult(
            request_id=request_id,
            ok=True,
            output={"path": "README.md", "content": "ok"},
            audit=CapabilityAudit(
                executor="desktop",
                started_at="2026-04-08T00:00:00+00:00",
                finished_at="2026-04-08T00:00:01+00:00",
                duration_ms=1000,
            ),
        )
    )

    second = CapabilityQueueStore(storage_path=storage)
    snapshot = second.get(request_id)
    assert snapshot is not None
    assert snapshot.status.value == "completed"
    assert snapshot.result is not None
    assert snapshot.result.ok is True

    dedup = second.dispatch(
        CapabilityDispatchRequest(
            capability="fs.read",
            args={"path": "README.md"},
            idempotency_key="persist-key",
        )
    )
    assert dedup.request.request_id == request_id


def test_capability_queue_persists_approval_history_events(tmp_path):
    storage = tmp_path / "capability-queue.json"
    first = CapabilityQueueStore(storage_path=storage)

    approved_record = first.dispatch(
        CapabilityDispatchRequest(
            capability="shell.run",
            args={"command": "echo approved"},
            requires_approval=True,
            idempotency_key="approval-persist-approved",
        )
    )
    assert first.approve_request(approved_record.request.request_id, approver="alice") is not None

    rejected_record = first.dispatch(
        CapabilityDispatchRequest(
            capability="shell.run",
            args={"command": "echo rejected"},
            requires_approval=True,
            idempotency_key="approval-persist-rejected",
        )
    )
    assert first.reject_request(
        rejected_record.request.request_id,
        approver="bob",
        reason="policy denied",
    ) is not None

    second = CapabilityQueueStore(storage_path=storage)
    events = second.list_approval_events(limit=10)
    assert len(events) >= 2
    assert any(event["action"] == "approved" and event["approver"] == "alice" for event in events)
    assert any(event["action"] == "rejected" and event["approver"] == "bob" for event in events)
