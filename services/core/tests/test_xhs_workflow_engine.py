from app.agent import xhs_workflow_engine as workflow_engine
from app.api.tool_capability_bridge import BrowserCapabilityError
from app.domain.models import XhsPublishMode, XhsWorkStatus
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


def test_publishing_without_publish_button_transitions_to_image_review(monkeypatch):
    engine = workflow_engine.XhsWorkDomainEngine(
        state_store=StateStore(),
        memory_repository=InMemoryMemoryRepository(),
    )
    domain = engine._get_or_init_domain()
    domain.state.status = XhsWorkStatus.PUBLISHING
    domain.profile.publish_mode = XhsPublishMode.DIRECT_PUBLISH
    domain.state.pending_drafts = [
        {
            "draft_id": "draft-1",
            "title": "高颜值巧克力怎么发",
            "body": "先拍开箱第一眼。\n\n再写口感和送礼场景。\n\n最后留一个互动问题。",
            "status": "pending",
        }
    ]
    engine._save(domain)

    monkeypatch.setattr(workflow_engine, "find_xiaohongshu_publish_button", lambda **kwargs: None)
    monkeypatch.setattr(
        workflow_engine,
        "autofill_xiaohongshu_text_image_cards",
        lambda *, cards, trigger_generate: type(
            "StubResult",
            (),
            {
                "status": "submitted_generation",
                "filled_cards": len(cards),
                "message": "已把 3/3 张图卡文案填进文字配图，并触发了生成图片。",
            },
        )(),
    )

    action = engine.tick()
    updated = engine.state_store.get().xhs_work_domain

    assert action is not None
    assert action.kind == "publishing"
    assert action.title == "已进入补图阶段"
    assert updated is not None
    assert updated.state.status == XhsWorkStatus.IDLE_REVIEWING
    assert updated.state.current_bottleneck == ""
    assert "触发生成图片" in updated.state.current_focus


def test_publishing_prefers_mcp_publish_with_generated_cover(monkeypatch):
    class _StubClient:
        pass

    engine = workflow_engine.XhsWorkDomainEngine(
        state_store=StateStore(),
        memory_repository=InMemoryMemoryRepository(),
        mcp_client=_StubClient(),  # type: ignore[arg-type]
    )
    domain = engine._get_or_init_domain()
    domain.state.status = XhsWorkStatus.PUBLISHING
    domain.profile.publish_mode = XhsPublishMode.DIRECT_PUBLISH
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

    monkeypatch.setattr(
        workflow_engine,
        "publish_xiaohongshu_image_post_via_mcp",
        lambda *, title, body, image_paths, client: type(
            "StubResult",
            (),
            {
                "status": "submitted",
                "message": "MCP 发布结果：已提交图文发布；已自动生成封面图。",
                "post_url": "https://www.xiaohongshu.com/explore/test",
                "image_paths": ["/tmp/generated-cover.png"],
            },
        )(),
    )

    action = engine.tick()
    updated = engine.state_store.get().xhs_work_domain

    assert action is not None
    assert action.kind == "publishing"
    assert action.title == "MCP 发布成功：高颜值巧克力怎么发"
    assert updated is not None
    assert updated.state.status == XhsWorkStatus.IDLE
    assert updated.state.backlog_count == 0
    assert updated.state.current_focus == "已通过 MCP 自动生成封面并发布图文"
    assert len(updated.state.pending_drafts) == 0
    assert len(updated.state.published_history) == 1


def test_publishing_falls_back_to_browser_with_generated_cover_when_mcp_unreachable(monkeypatch):
    engine = workflow_engine.XhsWorkDomainEngine(
        state_store=StateStore(),
        memory_repository=InMemoryMemoryRepository(),
    )
    domain = engine._get_or_init_domain()
    domain.state.status = XhsWorkStatus.PUBLISHING
    domain.profile.publish_mode = XhsPublishMode.DIRECT_PUBLISH
    domain.profile.auto_publish_selector = "button[type='submit']"
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

    monkeypatch.setattr(
        workflow_engine,
        "publish_xiaohongshu_image_post_via_mcp",
        lambda *, title, body, image_paths, client: type(
            "StubResult",
            (),
            {
                "status": "service_unreachable",
                "message": "MCP 发布失败：服务不可达。",
                "post_url": None,
                "image_paths": ["/tmp/generated-cover.png"],
            },
        )(),
    )

    def fake_call_browser_capability(capability, args, *, timeout_seconds=15.0):
        _ = timeout_seconds
        if capability == "browser.open":
            return {"session_id": "publish-session"}
        if capability == "browser.publish":
            assert args["image_paths"] == ["/tmp/generated-cover.png"]
            return {
                "status": "filled",
                "filled_title": True,
                "filled_body": True,
                "publish_clicked": True,
            }
        if capability == "browser.close":
            return {"status": "closed"}
        raise AssertionError(f"unexpected capability: {capability}")

    monkeypatch.setattr(workflow_engine, "call_browser_capability", fake_call_browser_capability)

    action = engine.tick()
    updated = engine.state_store.get().xhs_work_domain

    assert action is not None
    assert action.kind == "publishing"
    assert action.title == "发布成功：高颜值巧克力怎么发"
    assert updated is not None
    assert updated.state.status == XhsWorkStatus.IDLE
    assert updated.state.current_focus == "已自动补封面并发布成功"
    assert len(updated.state.pending_drafts) == 0
    assert len(updated.state.published_history) == 1


def test_idle_reviewing_resumes_pending_draft_and_finishes_publish(monkeypatch):
    engine = workflow_engine.XhsWorkDomainEngine(
        state_store=StateStore(),
        memory_repository=InMemoryMemoryRepository(),
    )
    domain = engine._get_or_init_domain()
    domain.state.status = XhsWorkStatus.IDLE_REVIEWING
    domain.profile.publish_mode = XhsPublishMode.DIRECT_PUBLISH
    domain.profile.auto_publish_selector = "button[type='submit']"
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

    monkeypatch.setattr(
        workflow_engine,
        "publish_xiaohongshu_image_post_via_mcp",
        lambda *, title, body, image_paths, client: type(
            "StubResult",
            (),
            {
                "status": "submitted",
                "message": "MCP 发布结果：已提交图文发布；已自动生成封面图。",
                "post_url": "https://www.xiaohongshu.com/explore/test",
                "image_paths": ["/tmp/generated-cover.png"],
            },
        )(),
    )

    action = engine.tick()
    updated = engine.state_store.get().xhs_work_domain

    assert action is not None
    assert action.kind == "publishing"
    assert action.title == "MCP 发布成功：高颜值巧克力怎么发"
    assert updated is not None
    assert updated.state.status == XhsWorkStatus.IDLE
    assert updated.state.current_bottleneck == ""
    assert len(updated.state.pending_drafts) == 0
    assert len(updated.state.published_history) == 1


def test_browser_publish_with_existing_images_returns_idle_instead_of_reviewing(monkeypatch):
    engine = workflow_engine.XhsWorkDomainEngine(
        state_store=StateStore(),
        memory_repository=InMemoryMemoryRepository(),
    )
    domain = engine._get_or_init_domain()
    domain.state.status = XhsWorkStatus.PUBLISHING
    domain.profile.publish_mode = XhsPublishMode.DIRECT_PUBLISH
    domain.profile.auto_publish_selector = "button[type='submit']"
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

    monkeypatch.setattr(
        workflow_engine,
        "publish_xiaohongshu_image_post_via_mcp",
        lambda *, title, body, image_paths, client: type(
            "StubResult",
            (),
            {
                "status": "service_unreachable",
                "message": "MCP 发布失败：服务不可达。",
                "post_url": None,
                "image_paths": [],
            },
        )(),
    )

    def fake_call_browser_capability(capability, args, *, timeout_seconds=15.0):
        _ = timeout_seconds
        if capability == "browser.open":
            return {"session_id": "publish-session"}
        if capability == "browser.publish":
            return {
                "status": "filled",
                "filled_title": True,
                "filled_body": True,
                "publish_clicked": True,
            }
        if capability == "browser.close":
            return {"status": "closed"}
        raise AssertionError(f"unexpected capability: {capability}")

    monkeypatch.setattr(workflow_engine, "call_browser_capability", fake_call_browser_capability)
    monkeypatch.setattr(
        workflow_engine,
        "generate_xiaohongshu_cover_image",
        lambda *, title, body: (_ for _ in ()).throw(workflow_engine.XiaohongshuCoverImageGenerationError("skip cover")),
    )

    action = engine.tick()
    updated = engine.state_store.get().xhs_work_domain

    assert action is not None
    assert action.kind == "publishing"
    assert updated is not None
    assert updated.state.status == XhsWorkStatus.IDLE
    assert updated.state.current_focus == "已完成补图并发布成功"


def test_review_before_publish_keeps_page_open_at_final_confirmation_step(monkeypatch):
    engine = workflow_engine.XhsWorkDomainEngine(
        state_store=StateStore(),
        memory_repository=InMemoryMemoryRepository(),
    )
    domain = engine._get_or_init_domain()
    domain.state.status = XhsWorkStatus.PUBLISHING
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

    closed_sessions: list[str] = []

    monkeypatch.setattr(
        workflow_engine,
        "publish_xiaohongshu_image_post_via_mcp",
        lambda *, title, body, image_paths, client: (_ for _ in ()).throw(AssertionError("mcp should be skipped")),
    )

    def fake_call_browser_capability(capability, args, *, timeout_seconds=15.0):
        _ = timeout_seconds
        if capability == "browser.open":
            return {"session_id": "review-session"}
        if capability == "browser.publish":
            assert args["publish_selector"] == ""
            assert args["image_paths"] == ["/tmp/generated-cover.png"]
            return {
                "status": "filled",
                "filled_title": True,
                "filled_body": True,
                "publish_clicked": False,
                "uploaded_image_count": 1,
                "upload_error": None,
            }
        if capability == "browser.close":
            closed_sessions.append(args["session_id"])
            return {"status": "closed"}
        raise AssertionError(f"unexpected capability: {capability}")

    monkeypatch.setattr(workflow_engine, "call_browser_capability", fake_call_browser_capability)
    monkeypatch.setattr(
        workflow_engine,
        "generate_xiaohongshu_cover_image",
        lambda *, title, body: type("StubCover", (), {"path": "/tmp/generated-cover.png"})(),
    )

    action = engine.tick()
    updated = engine.state_store.get().xhs_work_domain

    assert action is not None
    assert action.kind == "publishing"
    assert action.title == "已准备到发布前"
    assert updated is not None
    assert updated.state.status == XhsWorkStatus.REVIEWING
    assert updated.state.current_focus == "已上传并填好，停在发布前最后一步"
    assert updated.state.review_session_id == "review-session"
    assert updated.state.pending_drafts[0]["status"] == "ready_for_review"
    assert closed_sessions == []
