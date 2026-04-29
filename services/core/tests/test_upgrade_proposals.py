from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.agent.loop import AutonomyLoop
from app.api.deps import get_state_store
from app.domain.models import BeingState, FocusSubject, WakeMode
from app.main import app
from app.memory.models import MemoryEntry, MemoryEvent, MemoryKind
from app.memory.repository import InMemoryMemoryRepository
from app.runtime import StateStore
from app.upgrade_proposal.generator import build_upgrade_proposal


def _inner_memory(content: str) -> MemoryEvent:
    entry = MemoryEntry.create(
        kind=MemoryKind.EPISODIC,
        content=content,
        source_context="inner",
    )
    return MemoryEvent.from_entry(entry)


def test_upgrade_proposal_generation_keeps_saved_plan_with_focus_subject():
    now = datetime(2026, 4, 29, 21, 8, 12, tzinfo=timezone.utc)
    memory_repository = InMemoryMemoryRepository()
    for index in range(3):
        memory_repository.save_event(_inner_memory(f"我有点累，想先慢一点 {index}"))

    state_store = StateStore(
        BeingState(
            mode=WakeMode.AWAKE,
            focus_subject=FocusSubject(
                kind="lingering",
                title="还没收束的牵挂",
                why_now="这条线还挂着。",
            ),
        )
    )
    loop = AutonomyLoop(state_store, memory_repository, now_provider=lambda: now)
    state = state_store.get()
    recent_events = list(reversed(memory_repository.list_recent(limit=20)))
    world_state = loop._world_state_for(state, now)

    loop._maybe_generate_upgrade_proposal(state, recent_events, world_state, now)

    updated = state_store.get()
    assert len(updated.upgrade_proposals) == 1
    proposal = updated.upgrade_proposals[0]
    assert proposal.status == "submitted"
    assert proposal.category == "habit_adjustment"
    assert updated.last_upgrade_proposal_at == proposal.created_at
    assert updated.focus_subject is not None
    assert updated.focus_subject.kind == "upgrade_proposal"
    assert proposal.proposal_id in updated.focus_subject.why_now
    assert updated.focus_subject.source_ref == proposal.proposal_id


def test_upgrade_proposal_api_lists_and_updates_status():
    now = datetime(2026, 4, 29, 21, 8, 12, tzinfo=timezone.utc)
    state_store = StateStore(BeingState(mode=WakeMode.AWAKE))
    memory_repository = InMemoryMemoryRepository()
    loop = AutonomyLoop(state_store, memory_repository, now_provider=lambda: now)
    proposal = build_upgrade_proposal(
        motivation="最近状态不太好，inner memory 中多次表达疲惫",
        pain_points=["多次记录到疲惫状态", "仍有未完成的 focus"],
        observed_data={"tired_inner_count": 3},
        store=loop.upgrade_store,
        now=now,
    )
    assert proposal is not None
    proposal = loop.upgrade_store.save(proposal)
    app.dependency_overrides[get_state_store] = lambda: state_store
    client = TestClient(app)

    try:
        list_response = client.get("/upgrade-proposals")
        assert list_response.status_code == 200
        assert list_response.json()["total"] == 1
        assert list_response.json()["proposals"][0]["proposal_id"] == proposal.proposal_id

        approve_response = client.post(
            f"/upgrade-proposals/{proposal.proposal_id}/approve",
            json={"approver": "tester"},
        )
        assert approve_response.status_code == 200
        assert approve_response.json()["proposal"]["status"] == "approved"

        implement_response = client.post(f"/upgrade-proposals/{proposal.proposal_id}/implement")
        assert implement_response.status_code == 200
        assert implement_response.json()["proposal"]["status"] == "implemented"

        observe_response = client.post(
            f"/upgrade-proposals/{proposal.proposal_id}/observe",
            json={"result": "partial", "notes": "还需要观察"},
        )
        assert observe_response.status_code == 200
        body = observe_response.json()["proposal"]
        assert body["observation_result"] == "partial"
        assert body["observation_notes"] == "还需要观察"
    finally:
        app.dependency_overrides.clear()
