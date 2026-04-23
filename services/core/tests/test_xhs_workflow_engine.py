from datetime import datetime, timedelta, timezone

from app.agent import xhs_workflow_engine as workflow_engine
from app.api.tool_capability_bridge import BrowserCapabilityError
from app.domain.models import XhsPublishMode, XhsWorkStatus
from app.memory.repository import InMemoryMemoryRepository
from app.runtime import StateStore
import app.usecases.xiaohongshu_publish_pipeline as xhs_pipeline


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


def test_publishing_keeps_manual_review_as_the_only_publish_path(monkeypatch):
    engine = workflow_engine.XhsWorkDomainEngine(
        state_store=StateStore(),
        memory_repository=InMemoryMemoryRepository(),
    )
    domain = engine._get_or_init_domain()
    domain.state.status = XhsWorkStatus.PUBLISHING
    domain.profile.publish_mode = XhsPublishMode.MANUAL
    domain.state.pending_drafts = [
        {
            "draft_id": "draft-1",
            "title": "高颜值巧克力怎么发",
            "body": "先拍开箱第一眼。\n\n再写口感和送礼场景。\n\n最后留一个互动问题。",
            "status": "pending",
        }
    ]
    domain.state.backlog_count = 1
    engine._save(domain)

    def fake_call_browser_capability(capability, args, *, timeout_seconds=15.0):
        _ = timeout_seconds
        if capability == "browser.open":
            return {"session_id": "review-session"}
        if capability == "browser.publish":
            assert args["publish_selector"] == ""
            return {
                "status": "filled",
                "filled_title": True,
                "filled_body": True,
                "publish_clicked": False,
                "uploaded_image_count": 1,
            }
        raise AssertionError(f"unexpected capability: {capability}")

    monkeypatch.setattr(workflow_engine, "call_browser_capability", fake_call_browser_capability)

    action = engine.tick()
    updated = engine.state_store.get().xhs_work_domain

    assert action is not None
    assert action.kind == "publishing"
    assert action.title == "已准备到发布前"
    assert updated is not None
    assert updated.state.status == XhsWorkStatus.REVIEWING
    assert updated.state.review_session_id == "review-session"
    assert updated.state.current_focus == "已上传并填好，停在发布前最后一步"


def test_publishing_backfills_missing_body_before_generating_cover(monkeypatch):
    engine = workflow_engine.XhsWorkDomainEngine(
        state_store=StateStore(),
        memory_repository=InMemoryMemoryRepository(),
    )
    domain = engine._get_or_init_domain()
    domain.state.status = XhsWorkStatus.PUBLISHING
    domain.profile.publish_mode = XhsPublishMode.MANUAL
    domain.state.pending_drafts = [
        {
            "draft_id": "draft-1",
            "title": "收到礼物却有点失落",
            "body": "",
            "status": "pending",
            "source_kind": "topic",
            "opportunity_title": "#高颜值巧克力",
        }
    ]
    domain.state.backlog_count = 1
    engine._save(domain)

    captured = {}

    monkeypatch.setattr(
        xhs_pipeline,
        "generate_xiaohongshu_cover_image",
        lambda *, title, body: captured.update({"title": title, "body": body})
        or type("StubCover", (), {"path": "/tmp/generated-cover.png"})(),
    )

    def fake_call_browser_capability(capability, args, *, timeout_seconds=15.0):
        _ = timeout_seconds
        if capability == "browser.open":
            return {"session_id": "review-session"}
        if capability == "browser.publish":
            assert args["body"]
            return {
                "status": "filled",
                "filled_title": True,
                "filled_body": True,
                "publish_clicked": False,
                "uploaded_image_count": 1,
            }
        raise AssertionError(f"unexpected capability: {capability}")

    monkeypatch.setattr(workflow_engine, "call_browser_capability", fake_call_browser_capability)

    action = engine.tick()

    assert action is not None
    assert action.title == "已准备到发布前"
    assert "不是你太敏感" in captured["body"]


def test_blocked_recoverable_error_auto_resets_after_retry_interval():
    engine = workflow_engine.XhsWorkDomainEngine(
        state_store=StateStore(),
        memory_repository=InMemoryMemoryRepository(),
    )
    domain = engine._get_or_init_domain()
    domain.state.status = XhsWorkStatus.BLOCKED
    domain.state.blocked_reason = "页面快照失败"
    domain.state.blocked_at = datetime.now(timezone.utc) - timedelta(minutes=10)

    engine._check_and_fire_timer(domain)

    updated = engine.state_store.get().xhs_work_domain
    assert updated is not None
    assert updated.state.status == XhsWorkStatus.IDLE


def test_timer_fast_tracks_to_publishing_when_drafts_queued():
    engine = workflow_engine.XhsWorkDomainEngine(
        state_store=StateStore(),
        memory_repository=InMemoryMemoryRepository(),
    )
    domain = engine._get_or_init_domain()
    domain.state.status = XhsWorkStatus.IDLE
    domain.profile.publish_mode = XhsPublishMode.AUTO
    domain.state.pending_drafts = [
        {"draft_id": "d1", "title": "草稿1", "body": "...", "generated_at": "2024-01-01T00:00:00", "status": "pending"}
    ]
    domain.state.backlog_count = 1
    domain.state.last_published_at = None
    engine._save(domain)

    engine._check_and_fire_timer(domain)

    updated = engine.state_store.get().xhs_work_domain
    assert updated is not None
    assert updated.state.status == XhsWorkStatus.PUBLISHING
    assert updated.state.current_focus == "队列中有待发草稿，继续发布"


def test_timer_does_not_auto_publish_queued_drafts_in_manual_mode():
    engine = workflow_engine.XhsWorkDomainEngine(
        state_store=StateStore(),
        memory_repository=InMemoryMemoryRepository(),
    )
    domain = engine._get_or_init_domain()
    domain.state.status = XhsWorkStatus.IDLE
    domain.profile.publish_mode = XhsPublishMode.MANUAL
    domain.state.pending_drafts = [
        {"draft_id": "d1", "title": "草稿1", "body": "...", "generated_at": "2024-01-01T00:00:00", "status": "pending"}
    ]
    domain.state.backlog_count = 1
    domain.state.last_published_at = None
    domain.state.last_scouting_at = datetime.now(timezone.utc)
    engine._save(domain)

    engine._check_and_fire_timer(domain)

    updated = engine.state_store.get().xhs_work_domain
    assert updated is not None
    assert updated.state.status == XhsWorkStatus.IDLE


def test_auto_publish_mode_clicks_publish_and_marks_draft_published(monkeypatch):
    engine = workflow_engine.XhsWorkDomainEngine(
        state_store=StateStore(),
        memory_repository=InMemoryMemoryRepository(),
    )
    domain = engine._get_or_init_domain()
    domain.profile.publish_mode = XhsPublishMode.AUTO
    domain.state.status = XhsWorkStatus.PUBLISHING
    domain.state.pending_drafts = [
        {
            "draft_id": "draft-1",
            "title": "高颜值巧克力怎么发",
            "body": "先拍开箱第一眼。\n\n再写口感和送礼场景。\n\n最后留一个互动问题。",
            "status": "pending",
            "source_kind": "topic",
            "opportunity_title": "#高颜值巧克力",
        }
    ]
    domain.state.backlog_count = 1
    engine._save(domain)

    closed_sessions: list[str] = []

    def fake_call_browser_capability(capability, args, *, timeout_seconds=15.0):
        _ = timeout_seconds
        if capability == "browser.open":
            if args["url"].endswith("target=image") and not closed_sessions:
                return {"session_id": "selector-session"}
            return {"session_id": "publish-session"}
        if capability == "browser.find_publish_button":
            assert args["session_id"] == "selector-session"
            return {"found": True, "selector": "button.submit"}
        if capability == "browser.publish":
            assert args["publish_selector"] == "button.submit"
            return {
                "status": "filled",
                "filled_title": True,
                "filled_body": True,
                "publish_clicked": True,
                "uploaded_image_count": 1,
            }
        if capability == "browser.close":
            closed_sessions.append(args["session_id"])
            return {"ok": True}
        raise AssertionError(f"unexpected capability: {capability}")

    monkeypatch.setattr(workflow_engine, "call_browser_capability", fake_call_browser_capability)

    action = engine.tick()
    updated = engine.state_store.get().xhs_work_domain

    assert action is not None
    assert action.kind == "publishing"
    assert action.title.startswith("发布成功：")
    assert updated is not None
    assert updated.state.status == XhsWorkStatus.IDLE
    assert updated.state.backlog_count == 0
    assert len(updated.state.pending_drafts) == 0
    assert len(updated.state.published_history) == 1
    assert updated.state.published_history[0]["title"] == "高颜值巧克力怎么发"
    assert closed_sessions == ["selector-session", "publish-session"]


def test_manual_mode_drafting_stops_after_generating_drafts(monkeypatch):
    engine = workflow_engine.XhsWorkDomainEngine(
        state_store=StateStore(),
        memory_repository=InMemoryMemoryRepository(),
    )
    domain = engine._get_or_init_domain()
    domain.profile.publish_mode = XhsPublishMode.MANUAL
    domain.state.status = XhsWorkStatus.DRAFTING
    domain.state.last_scouting_data = {"topics": [{"topic": "#高颜值巧克力"}], "activities": []}
    engine._save(domain)

    monkeypatch.setattr(
        workflow_engine,
        "build_xiaohongshu_opportunity_items",
        lambda *args, **kwargs: [{"title": "#高颜值巧克力", "summary": "轻科普机会", "source_kind": "topic"}],
    )
    monkeypatch.setattr(
        workflow_engine,
        "generate_xiaohongshu_draft_from_opportunity",
        lambda opportunity, gateway, build_prompt: type(
            "DraftOutcome",
            (),
            {
                "draft": {
                    "draft_id": "draft-1",
                    "title": "巧克力轻科普",
                    "body": "先讲一个会被忽略的情绪瞬间。",
                    "status": "pending",
                },
                "action_title": "巧克力轻科普",
            },
        )(),
    )

    action = engine.tick()
    updated = engine.state_store.get().xhs_work_domain

    assert action is not None
    assert action.kind == "drafting"
    assert updated is not None
    assert updated.state.status == XhsWorkStatus.IDLE
    assert updated.state.backlog_count == 1
    assert updated.state.current_focus == "已生成 1 条草稿，等待手动发布"
    assert updated.state.next_recommended_action == "请在待发草稿列表中选择一条并点击发布。"
