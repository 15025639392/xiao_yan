from fastapi.testclient import TestClient
from datetime import datetime, timedelta, timezone
import time

from app.api.capabilities_routes import _reset_capability_queue_for_tests
from app.capabilities.models import CapabilityDispatchRequest
from app.capabilities.runtime import dispatch_and_wait, get_capability_queue
from app.main import app


def test_capability_queue_dispatch_claim_complete_roundtrip():
    _reset_capability_queue_for_tests()
    client = TestClient(app)

    dispatch_resp = client.post(
        "/capabilities/dispatch",
        json={
            "capability": "fs.read",
            "args": {"path": "README.md"},
            "context": {"reason": "test roundtrip"},
        },
    )
    assert dispatch_resp.status_code == 200
    request_id = dispatch_resp.json()["request_id"]

    pending_resp = client.get("/capabilities/pending?executor=desktop&limit=5")
    assert pending_resp.status_code == 200
    items = pending_resp.json()["items"]
    assert len(items) == 1
    pending_request = items[0]["request"]
    assert pending_request["request_id"] == request_id
    assert pending_request["capability"] == "fs.read"

    complete_resp = client.post(
        "/capabilities/complete",
        json={
            "request_id": request_id,
            "ok": True,
            "output": {"path": "README.md", "content": "ok"},
            "audit": {
                "executor": "desktop",
                "started_at": "2026-04-08T00:00:00+00:00",
                "finished_at": "2026-04-08T00:00:01+00:00",
                "duration_ms": 1000,
            },
        },
    )
    assert complete_resp.status_code == 200
    assert complete_resp.json()["status"] == "completed"

    result_resp = client.get(f"/capabilities/result/{request_id}")
    assert result_resp.status_code == 200
    payload = result_resp.json()
    assert payload["status"] == "completed"
    assert payload["result"]["ok"] is True
    assert payload["result"]["output"]["path"] == "README.md"

    status_resp = client.get("/capabilities/queue/status")
    assert status_resp.status_code == 200
    status_payload = status_resp.json()
    assert status_payload["pending"] == 0
    assert status_payload["completed"] == 1


def test_complete_unknown_capability_request_returns_404():
    _reset_capability_queue_for_tests()
    client = TestClient(app)

    response = client.post(
        "/capabilities/complete",
        json={
            "request_id": "missing-id",
            "ok": False,
            "error_code": "not_found",
            "error_message": "missing",
            "audit": {
                "executor": "desktop",
                "started_at": "2026-04-08T00:00:00+00:00",
                "finished_at": "2026-04-08T00:00:00+00:00",
                "duration_ms": 0,
            },
        },
    )
    assert response.status_code == 404


def test_dispatch_timeout_fallback_marks_request_completed():
    _reset_capability_queue_for_tests()
    result = dispatch_and_wait(
        CapabilityDispatchRequest(
            capability="fs.read",
            args={"path": "README.md"},
        ),
        timeout_seconds=0.05,
        poll_interval_seconds=0.01,
    )
    assert result is None

    queue = get_capability_queue()
    status = queue.status_counts()
    assert status["pending"] == 0
    assert status["completed"] == 1


def test_capability_heartbeat_marks_executor_online():
    _reset_capability_queue_for_tests()
    client = TestClient(app)

    heartbeat_resp = client.post("/capabilities/heartbeat?executor=desktop")
    assert heartbeat_resp.status_code == 200
    assert heartbeat_resp.json()["executor"] == "desktop"


def test_capability_jobs_endpoint_exposes_policy_revision_and_executor():
    _reset_capability_queue_for_tests()
    client = TestClient(app)

    dispatch_resp = client.post(
        "/capabilities/dispatch",
        json={
            "capability": "shell.run",
            "args": {
                "command": "echo hello",
                "policy_version": "2026-04-08-v1",
                "policy_revision": 7,
            },
        },
    )
    assert dispatch_resp.status_code == 200
    request_id = dispatch_resp.json()["request_id"]

    complete_resp = client.post(
        "/capabilities/complete",
        json={
            "request_id": request_id,
            "ok": False,
            "error_code": "not_supported",
            "audit": {
                "executor": "desktop",
                "started_at": "2026-04-08T00:00:00+00:00",
                "finished_at": "2026-04-08T00:00:01+00:00",
                "duration_ms": 1000,
            },
        },
    )
    assert complete_resp.status_code == 200

    jobs_resp = client.get("/capabilities/jobs?limit=5&status=completed")
    assert jobs_resp.status_code == 200
    items = jobs_resp.json()["items"]
    assert len(items) >= 1
    latest = items[0]
    assert latest["request_id"] == request_id
    assert latest["capability"] == "shell.run"
    assert latest["policy_version"] == "2026-04-08-v1"
    assert latest["policy_revision"] == 7
    assert latest["executor"] == "desktop"
    assert latest["error_code"] == "not_supported"


def test_capability_dispatch_with_idempotency_key_deduplicates_requests():
    _reset_capability_queue_for_tests()
    client = TestClient(app)

    first = client.post(
        "/capabilities/dispatch",
        json={
            "capability": "fs.read",
            "args": {"path": "README.md"},
            "idempotency_key": "same-key",
        },
    )
    assert first.status_code == 200
    first_request_id = first.json()["request_id"]

    second = client.post(
        "/capabilities/dispatch",
        json={
            "capability": "fs.read",
            "args": {"path": "README.md"},
            "idempotency_key": "same-key",
        },
    )
    assert second.status_code == 200
    assert second.json()["request_id"] == first_request_id


def test_capability_retryable_failure_requeues_until_dead_letter():
    _reset_capability_queue_for_tests()
    client = TestClient(app)

    dispatch_resp = client.post(
        "/capabilities/dispatch",
        json={
            "capability": "shell.run",
            "args": {"command": "echo hello"},
            "requires_approval": False,
            "max_attempts": 2,
        },
    )
    assert dispatch_resp.status_code == 200
    request_id = dispatch_resp.json()["request_id"]

    pending_first = client.get("/capabilities/pending?executor=desktop&limit=1")
    assert pending_first.status_code == 200
    first_item = pending_first.json()["items"][0]
    assert first_item["request"]["attempt"] == 1

    first_fail = client.post(
        "/capabilities/complete",
        json={
            "request_id": request_id,
            "ok": False,
            "error_code": "execution_error",
            "error_message": "transient failure",
            "audit": {
                "executor": "desktop",
                "started_at": "2026-04-08T00:00:00+00:00",
                "finished_at": "2026-04-08T00:00:01+00:00",
                "duration_ms": 1000,
            },
        },
    )
    assert first_fail.status_code == 200
    assert first_fail.json()["status"] == "pending"
    assert first_fail.json()["completed_at"] is None

    pending_second = client.get("/capabilities/pending?executor=desktop&limit=1")
    assert pending_second.status_code == 200
    second_item = pending_second.json()["items"][0]
    assert second_item["request"]["attempt"] == 2

    second_fail = client.post(
        "/capabilities/complete",
        json={
            "request_id": request_id,
            "ok": False,
            "error_code": "execution_error",
            "error_message": "transient failure again",
            "audit": {
                "executor": "desktop",
                "started_at": "2026-04-08T00:00:02+00:00",
                "finished_at": "2026-04-08T00:00:03+00:00",
                "duration_ms": 1000,
            },
        },
    )
    assert second_fail.status_code == 200
    assert second_fail.json()["status"] == "completed"
    assert second_fail.json()["completed_at"] is not None

    status = client.get("/capabilities/queue/status")
    assert status.status_code == 200
    assert status.json()["dead_letter"] == 1

    jobs = client.get("/capabilities/jobs?dead_letter_only=true&limit=5")
    assert jobs.status_code == 200
    items = jobs.json()["items"]
    assert len(items) >= 1
    latest = items[0]
    assert latest["request_id"] == request_id
    assert latest["dead_letter"] is True
    assert latest["attempt"] == 2
    assert latest["max_attempts"] == 2


def test_requeue_dead_letter_endpoint_restores_pending_state():
    _reset_capability_queue_for_tests()
    client = TestClient(app)

    dispatch_resp = client.post(
        "/capabilities/dispatch",
        json={
            "capability": "shell.run",
            "args": {"command": "echo hello"},
            "requires_approval": False,
            "max_attempts": 1,
        },
    )
    assert dispatch_resp.status_code == 200
    request_id = dispatch_resp.json()["request_id"]

    claim = client.get("/capabilities/pending?executor=desktop&limit=1")
    assert claim.status_code == 200
    assert claim.json()["items"][0]["request"]["request_id"] == request_id

    fail = client.post(
        "/capabilities/complete",
        json={
            "request_id": request_id,
            "ok": False,
            "error_code": "execution_error",
            "error_message": "dead-letter me",
            "audit": {
                "executor": "desktop",
                "started_at": "2026-04-08T00:00:00+00:00",
                "finished_at": "2026-04-08T00:00:01+00:00",
                "duration_ms": 1000,
            },
        },
    )
    assert fail.status_code == 200
    assert fail.json()["status"] == "completed"

    requeue = client.post(f"/capabilities/dead-letter/requeue/{request_id}")
    assert requeue.status_code == 200
    assert requeue.json()["status"] == "pending"

    claim_again = client.get("/capabilities/pending?executor=desktop&limit=1")
    assert claim_again.status_code == 200
    assert claim_again.json()["items"][0]["request"]["attempt"] == 1


def test_requires_approval_job_must_be_approved_before_claim():
    _reset_capability_queue_for_tests()
    client = TestClient(app)

    dispatch_resp = client.post(
        "/capabilities/dispatch",
        json={
            "capability": "shell.run",
            "args": {"command": "echo hello"},
            "requires_approval": True,
            "idempotency_key": "approval-case-1",
        },
    )
    assert dispatch_resp.status_code == 200
    request_id = dispatch_resp.json()["request_id"]

    pending_before = client.get("/capabilities/pending?executor=desktop&limit=5")
    assert pending_before.status_code == 200
    assert all(item["request"]["request_id"] != request_id for item in pending_before.json()["items"])

    approvals = client.get("/capabilities/approvals/pending?limit=5")
    assert approvals.status_code == 200
    items = approvals.json()["items"]
    assert any(item["request"]["request_id"] == request_id for item in items)

    approve = client.post(
        f"/capabilities/approvals/{request_id}/approve",
        json={"approver": "tester"},
    )
    assert approve.status_code == 200
    assert approve.json()["approval_status"] == "approved"

    pending_after = client.get("/capabilities/pending?executor=desktop&limit=5")
    assert pending_after.status_code == 200
    assert any(item["request"]["request_id"] == request_id for item in pending_after.json()["items"])


def test_rejecting_approval_marks_job_completed_with_rejection_error():
    _reset_capability_queue_for_tests()
    client = TestClient(app)

    dispatch_resp = client.post(
        "/capabilities/dispatch",
        json={
            "capability": "shell.run",
            "args": {"command": "echo hello"},
            "requires_approval": True,
            "idempotency_key": "approval-case-2",
        },
    )
    assert dispatch_resp.status_code == 200
    request_id = dispatch_resp.json()["request_id"]

    reject = client.post(
        f"/capabilities/approvals/{request_id}/reject",
        json={"approver": "tester", "reason": "denied by policy"},
    )
    assert reject.status_code == 200
    assert reject.json()["approval_status"] == "rejected"
    assert reject.json()["status"] == "completed"

    result = client.get(f"/capabilities/result/{request_id}")
    assert result.status_code == 200
    payload = result.json()
    assert payload["status"] == "completed"
    assert payload["result"]["ok"] is False
    assert payload["result"]["error_code"] == "approval_rejected"

    pending = client.get("/capabilities/pending?executor=desktop&limit=5")
    assert pending.status_code == 200
    assert all(item["request"]["request_id"] != request_id for item in pending.json()["items"])


def test_approval_history_records_decisions_and_supports_filters():
    _reset_capability_queue_for_tests()
    client = TestClient(app)

    approved_dispatch = client.post(
        "/capabilities/dispatch",
        json={
            "capability": "shell.run",
            "args": {"command": "echo approved"},
            "requires_approval": True,
            "idempotency_key": "approval-history-approved",
        },
    )
    assert approved_dispatch.status_code == 200
    approved_request_id = approved_dispatch.json()["request_id"]

    approved = client.post(
        f"/capabilities/approvals/{approved_request_id}/approve",
        json={"approver": "alice"},
    )
    assert approved.status_code == 200
    assert approved.json()["approval_status"] == "approved"

    rejected_dispatch = client.post(
        "/capabilities/dispatch",
        json={
            "capability": "shell.run",
            "args": {"command": "echo rejected"},
            "requires_approval": True,
            "idempotency_key": "approval-history-rejected",
        },
    )
    assert rejected_dispatch.status_code == 200
    rejected_request_id = rejected_dispatch.json()["request_id"]

    rejected = client.post(
        f"/capabilities/approvals/{rejected_request_id}/reject",
        json={"approver": "bob", "reason": "policy denied"},
    )
    assert rejected.status_code == 200
    assert rejected.json()["approval_status"] == "rejected"

    history_all = client.get("/capabilities/approvals/history?limit=10")
    assert history_all.status_code == 200
    all_items = history_all.json()["items"]
    assert len(all_items) >= 2
    assert any(item["request_id"] == approved_request_id and item["action"] == "approved" for item in all_items)
    assert any(item["request_id"] == rejected_request_id and item["action"] == "rejected" for item in all_items)

    history_rejected = client.get("/capabilities/approvals/history?action=rejected&limit=10")
    assert history_rejected.status_code == 200
    rejected_items = history_rejected.json()["items"]
    assert len(rejected_items) >= 1
    assert all(item["action"] == "rejected" for item in rejected_items)
    assert any(item["request_id"] == rejected_request_id for item in rejected_items)

    history_by_approver = client.get("/capabilities/approvals/history?approver=bob&limit=10")
    assert history_by_approver.status_code == 200
    bob_items = history_by_approver.json()["items"]
    assert len(bob_items) >= 1
    assert all(item["approver"] == "bob" for item in bob_items)
    assert any(item["request_id"] == rejected_request_id for item in bob_items)


def test_capability_jobs_supports_approval_related_filters():
    _reset_capability_queue_for_tests()
    client = TestClient(app)

    approved_dispatch = client.post(
        "/capabilities/dispatch",
        json={
            "capability": "shell.run",
            "args": {"command": "echo approved"},
            "requires_approval": True,
            "idempotency_key": "jobs-filter-approved",
        },
    )
    assert approved_dispatch.status_code == 200
    approved_request_id = approved_dispatch.json()["request_id"]
    approved = client.post(
        f"/capabilities/approvals/{approved_request_id}/approve",
        json={"approver": "alice"},
    )
    assert approved.status_code == 200

    rejected_dispatch = client.post(
        "/capabilities/dispatch",
        json={
            "capability": "shell.run",
            "args": {"command": "echo rejected"},
            "requires_approval": True,
            "idempotency_key": "jobs-filter-rejected",
        },
    )
    assert rejected_dispatch.status_code == 200
    rejected_request_id = rejected_dispatch.json()["request_id"]
    rejected = client.post(
        f"/capabilities/approvals/{rejected_request_id}/reject",
        json={"approver": "bob", "reason": "policy denied"},
    )
    assert rejected.status_code == 200

    no_approval_dispatch = client.post(
        "/capabilities/dispatch",
        json={
            "capability": "fs.read",
            "args": {"path": "README.md"},
            "requires_approval": False,
            "idempotency_key": "jobs-filter-no-approval",
        },
    )
    assert no_approval_dispatch.status_code == 200

    approved_only = client.get("/capabilities/jobs?approval_status=approved&limit=20")
    assert approved_only.status_code == 200
    approved_items = approved_only.json()["items"]
    assert len(approved_items) >= 1
    assert all(item["approval_status"] == "approved" for item in approved_items)
    assert any(item["request_id"] == approved_request_id for item in approved_items)

    bob_only = client.get("/capabilities/jobs?approver=bob&limit=20")
    assert bob_only.status_code == 200
    bob_items = bob_only.json()["items"]
    assert len(bob_items) >= 1
    assert all(item["request_id"] == rejected_request_id for item in bob_items)

    exact = client.get(
        f"/capabilities/jobs?capability=shell.run&request_id={approved_request_id}&approval_status=approved&limit=20"
    )
    assert exact.status_code == 200
    exact_items = exact.json()["items"]
    assert len(exact_items) == 1
    assert exact_items[0]["request_id"] == approved_request_id


def _find_job(items: list[dict], request_id: str) -> dict:
    return next(item for item in items if item["request_id"] == request_id)


def test_capability_jobs_supports_time_window_filters():
    _reset_capability_queue_for_tests()
    client = TestClient(app)

    first = client.post(
        "/capabilities/dispatch",
        json={"capability": "fs.read", "args": {"path": "README.md"}, "idempotency_key": "time-filter-1"},
    )
    assert first.status_code == 200
    first_id = first.json()["request_id"]

    time.sleep(0.05)

    second = client.post(
        "/capabilities/dispatch",
        json={"capability": "fs.read", "args": {"path": "README.md"}, "idempotency_key": "time-filter-2"},
    )
    assert second.status_code == 200
    second_id = second.json()["request_id"]

    first_complete = client.post(
        "/capabilities/complete",
        json={
            "request_id": first_id,
            "ok": True,
            "output": {"path": "README.md", "content": "ok"},
            "audit": {
                "executor": "desktop",
                "started_at": "2026-04-08T00:00:00+00:00",
                "finished_at": "2026-04-08T00:00:01+00:00",
                "duration_ms": 1000,
            },
        },
    )
    assert first_complete.status_code == 200

    time.sleep(0.05)

    second_complete = client.post(
        "/capabilities/complete",
        json={
            "request_id": second_id,
            "ok": True,
            "output": {"path": "README.md", "content": "ok"},
            "audit": {
                "executor": "desktop",
                "started_at": "2026-04-08T00:00:02+00:00",
                "finished_at": "2026-04-08T00:00:03+00:00",
                "duration_ms": 1000,
            },
        },
    )
    assert second_complete.status_code == 200

    all_jobs = client.get("/capabilities/jobs?limit=20")
    assert all_jobs.status_code == 200
    all_items = all_jobs.json()["items"]
    first_job = _find_job(all_items, first_id)
    second_job = _find_job(all_items, second_id)

    first_queued = datetime.fromisoformat(first_job["queued_at"])
    second_queued = datetime.fromisoformat(second_job["queued_at"])
    first_completed = datetime.fromisoformat(first_job["completed_at"])
    second_completed = datetime.fromisoformat(second_job["completed_at"])

    queued_from = (second_queued - timedelta(milliseconds=5)).isoformat()
    queued_only_second = client.get("/capabilities/jobs", params={"limit": 20, "queued_from": queued_from})
    assert queued_only_second.status_code == 200
    queued_second_ids = {item["request_id"] for item in queued_only_second.json()["items"]}
    assert second_id in queued_second_ids
    assert first_id not in queued_second_ids

    queued_to = (first_queued + timedelta(milliseconds=5)).isoformat()
    queued_only_first = client.get("/capabilities/jobs", params={"limit": 20, "queued_to": queued_to})
    assert queued_only_first.status_code == 200
    queued_first_ids = {item["request_id"] for item in queued_only_first.json()["items"]}
    assert first_id in queued_first_ids
    assert second_id not in queued_first_ids

    completed_from = (second_completed - timedelta(milliseconds=5)).isoformat()
    completed_only_second = client.get("/capabilities/jobs", params={"limit": 20, "completed_from": completed_from})
    assert completed_only_second.status_code == 200
    completed_second_ids = {item["request_id"] for item in completed_only_second.json()["items"]}
    assert second_id in completed_second_ids
    assert first_id not in completed_second_ids

    completed_to = (first_completed + timedelta(milliseconds=5)).isoformat()
    completed_only_first = client.get("/capabilities/jobs", params={"limit": 20, "completed_to": completed_to})
    assert completed_only_first.status_code == 200
    completed_first_ids = {item["request_id"] for item in completed_only_first.json()["items"]}
    assert first_id in completed_first_ids
    assert second_id not in completed_first_ids


def test_capability_jobs_supports_cursor_pagination():
    _reset_capability_queue_for_tests()
    client = TestClient(app)

    ids: list[str] = []
    for idx in range(3):
        dispatch = client.post(
            "/capabilities/dispatch",
            json={
                "capability": "fs.read",
                "args": {"path": f"README-{idx}.md"},
                "idempotency_key": f"jobs-cursor-{idx}",
            },
        )
        assert dispatch.status_code == 200
        ids.append(dispatch.json()["request_id"])
        time.sleep(0.02)

    first_page = client.get("/capabilities/jobs?limit=1")
    assert first_page.status_code == 200
    payload_1 = first_page.json()
    assert len(payload_1["items"]) == 1
    assert payload_1["next_cursor"] is not None
    first_id = payload_1["items"][0]["request_id"]

    second_page = client.get(f"/capabilities/jobs?limit=1&cursor={payload_1['next_cursor']}")
    assert second_page.status_code == 200
    payload_2 = second_page.json()
    assert len(payload_2["items"]) == 1
    assert payload_2["items"][0]["request_id"] != first_id

    third_page = client.get(f"/capabilities/jobs?limit=1&cursor={payload_2['next_cursor']}")
    assert third_page.status_code == 200
    payload_3 = third_page.json()
    assert len(payload_3["items"]) == 1
    assert payload_3["next_cursor"] is None
    paged_ids = {first_id, payload_2["items"][0]["request_id"], payload_3["items"][0]["request_id"]}
    assert paged_ids.issuperset(set(ids))
