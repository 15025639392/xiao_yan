from app.agent import xhs_workflow_engine as workflow_engine
from app.api.tool_capability_bridge import BrowserCapabilityError
from app.domain.models import XhsWorkStatus
from app.memory.repository import InMemoryMemoryRepository
from app.runtime import StateStore


def test_scouting_open_failure_blocks_instead_of_crashing(monkeypatch):
    engine = workflow_engine.XhsWorkDomainEngine(
        state_store=StateStore(),
        memory_repository=InMemoryMemoryRepository(),
    )
    domain = engine._get_or_init_domain()
    domain.state.status = XhsWorkStatus.SCOUTING
    engine._save(domain)

    def fake_call_browser_capability(capability, args, *, timeout_seconds=15.0):
        _ = (capability, args, timeout_seconds)
        raise BrowserCapabilityError("driver error")

    monkeypatch.setattr(workflow_engine, "call_browser_capability", fake_call_browser_capability)

    action = engine.tick()
    updated = engine.state_store.get().xhs_work_domain

    assert action is not None
    assert action.kind == "scouting"
    assert action.data["error"] == "browser open failed"
    assert updated is not None
    assert updated.state.status == XhsWorkStatus.BLOCKED
    assert updated.state.current_bottleneck == "打不开创作首页"
