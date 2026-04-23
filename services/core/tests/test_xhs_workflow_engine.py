from datetime import datetime, timedelta, timezone

from app.agent import xhs_workflow_engine as workflow_engine
from app.api.tool_capability_bridge import BrowserCapabilityError
from app.domain.models import XhsPublishMode, XhsWorkStatus
from app.memory.repository import InMemoryMemoryRepository
from app.runtime import StateStore
import app.usecases.xiaohongshu_publish_pipeline as xhs_pipeline
from app.usecases.xiaohongshu_cover_image import XiaohongshuCoverImageGenerationError


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


def test_publishing_without_publish_button_blocks_instead_of_entering_text_image(monkeypatch):
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

    monkeypatch.setattr(xhs_pipeline, "find_xiaohongshu_publish_button", lambda **kwargs: None)
    action = engine.tick()
    updated = engine.state_store.get().xhs_work_domain

    assert action is not None
    assert action.kind == "publishing"
    assert action.title == "发布失败"
    assert updated is not None
    assert updated.state.status == XhsWorkStatus.BLOCKED
    assert updated.state.current_bottleneck == "找不到发布按钮"


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
        xhs_pipeline,
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
        xhs_pipeline,
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
        xhs_pipeline,
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
        xhs_pipeline,
        "generate_xiaohongshu_cover_image",
        lambda *, title, body: (_ for _ in ()).throw(XiaohongshuCoverImageGenerationError("skip cover")),
    )

    action = engine.tick()
    updated = engine.state_store.get().xhs_work_domain

    assert action is not None
    assert action.kind == "publishing"
    assert updated is not None
    assert updated.state.status == XhsWorkStatus.BLOCKED
    assert updated.state.current_bottleneck == "缺少可上传封面"


def test_publishing_backfills_missing_body_before_generating_cover(monkeypatch):
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
            "title": "收到礼物却有点失落",
            "body": "",
            "status": "pending",
            "source_kind": "topic",
            "opportunity_title": "#高颜值巧克力",
        }
    ]
    domain.state.backlog_count = 1
    engine._save(domain)

    monkeypatch.setattr(
        xhs_pipeline,
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
            return {"session_id": "publish-session"}
        if capability == "browser.publish":
            assert args["image_paths"] == ["/tmp/generated-cover.png"]
            assert args["body"]
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
    assert action.title == "发布成功：收到礼物却有点失落"
    assert "不是你太敏感" in captured["body"]
    assert updated is not None
    assert updated.state.status == XhsWorkStatus.IDLE


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
        xhs_pipeline,
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
        xhs_pipeline,
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


def test_preparing_status_removed():
    assert not any(m.value == "preparing" for m in XhsWorkStatus)


def test_drafting_uses_persisted_scouting_data_after_restart(monkeypatch):
    state_store = StateStore()
    engine1 = workflow_engine.XhsWorkDomainEngine(
        state_store=state_store,
        memory_repository=InMemoryMemoryRepository(),
    )
    domain = engine1._get_or_init_domain()
    domain.state.status = XhsWorkStatus.SCOUTING
    engine1._save(domain)

    def fake_call_browser_capability(capability, args, *, timeout_seconds=15.0):
        _ = timeout_seconds
        if capability == "browser.open":
            return {"session_id": "scout-session"}
        if capability == "browser.snapshot":
            return {"text_content": "创作话题\n#高颜值巧克力\n活动\nRED新生代创作大赛"}
        if capability == "browser.close":
            return {"status": "closed"}
        raise AssertionError(f"unexpected capability: {capability}")

    monkeypatch.setattr(workflow_engine, "call_browser_capability", fake_call_browser_capability)

    engine1.tick()
    updated = state_store.get().xhs_work_domain
    assert updated is not None
    assert updated.state.status == XhsWorkStatus.DRAFTING
    assert updated.state.last_scouting_data != {}

    # Simulate service restart: create a fresh engine with the same state_store
    engine2 = workflow_engine.XhsWorkDomainEngine(
        state_store=state_store,
        memory_repository=InMemoryMemoryRepository(),
    )

    action = engine2.tick()
    updated2 = state_store.get().xhs_work_domain
    assert action is not None
    assert action.kind == "drafting"
    assert "草稿" in action.title
    assert updated2 is not None
    assert updated2.state.status == XhsWorkStatus.PUBLISHING


def test_build_draft_prompt_includes_persona_fields():
    engine = workflow_engine.XhsWorkDomainEngine(
        state_store=StateStore(),
        memory_repository=InMemoryMemoryRepository(),
    )
    domain = engine._get_or_init_domain()
    domain.profile.account_positioning = "生活方式博主"
    domain.profile.target_audience = "25-35岁都市女性"
    domain.profile.expression_style = "温暖亲切，像朋友聊天"
    engine._save(domain)

    prompt = engine._build_draft_prompt(
        {"title": "测试话题", "summary": "测试摘要", "source_kind": "topic"}
    )

    assert "账号定位：生活方式博主" in prompt
    assert "目标受众：25-35岁都市女性" in prompt
    assert "表达风格：温暖亲切，像朋友聊天" in prompt


def test_build_draft_prompt_uses_default_light_science_persona_fields():
    engine = workflow_engine.XhsWorkDomainEngine(
        state_store=StateStore(),
        memory_repository=InMemoryMemoryRepository(),
    )
    prompt = engine._build_draft_prompt(
        {"title": "测试话题", "summary": "测试摘要", "source_kind": "topic"}
    )

    assert "账号定位：数字生命式情绪关系轻科普" in prompt
    assert "目标受众：在情绪、关系和自我认知里需要被理解与陪伴的年轻用户" in prompt
    assert "表达风格：像小晏一样温和、具体、先接住再解释" in prompt


def test_blocked_recoverable_error_auto_resets_after_retry_interval():
    engine = workflow_engine.XhsWorkDomainEngine(
        state_store=StateStore(),
        memory_repository=InMemoryMemoryRepository(),
    )
    domain = engine._get_or_init_domain()
    domain.state.status = XhsWorkStatus.BLOCKED
    domain.state.blocked_reason = "浏览器器官不可用"
    domain.state.blocked_at = datetime.now(timezone.utc) - timedelta(seconds=workflow_engine._BLOCKED_RETRY_SECONDS + 1)
    engine._save(domain)
    engine._is_first_tick = False

    action = engine.tick()
    updated = engine.state_store.get().xhs_work_domain

    assert action is None
    assert updated is not None
    assert updated.state.status == XhsWorkStatus.IDLE
    assert updated.state.blocked_reason == ""
    assert updated.state.current_bottleneck == ""


def test_blocked_non_recoverable_error_stays_blocked():
    engine = workflow_engine.XhsWorkDomainEngine(
        state_store=StateStore(),
        memory_repository=InMemoryMemoryRepository(),
    )
    domain = engine._get_or_init_domain()
    domain.state.status = XhsWorkStatus.BLOCKED
    domain.state.blocked_reason = "需要登录小红书账号"
    domain.state.blocked_at = datetime.now(timezone.utc) - timedelta(seconds=workflow_engine._BLOCKED_RETRY_SECONDS + 1)
    engine._save(domain)
    engine._is_first_tick = False

    action = engine.tick()
    updated = engine.state_store.get().xhs_work_domain

    assert action is None
    assert updated is not None
    assert updated.state.status == XhsWorkStatus.BLOCKED
    assert updated.state.blocked_reason == "需要登录小红书账号"


def test_drafting_appends_to_existing_queue(monkeypatch):
    engine = workflow_engine.XhsWorkDomainEngine(
        state_store=StateStore(),
        memory_repository=InMemoryMemoryRepository(),
    )
    domain = engine._get_or_init_domain()
    domain.state.status = XhsWorkStatus.DRAFTING
    domain.state.pending_drafts = [
        {"draft_id": "existing", "title": "已有草稿", "body": "...", "generated_at": "2024-01-01T00:00:00", "status": "pending"}
    ]
    domain.state.last_scouting_data = {
        "topics": [{"topic": "#新话题", "participation_count": "1万", "view_count": "10万"}],
        "activities": [],
    }
    engine._save(domain)

    monkeypatch.setattr(
        workflow_engine,
        "generate_xiaohongshu_draft_from_opportunity",
        lambda opportunity, *, gateway, build_prompt: type(
            "Outcome",
            (),
            {
                "draft": {
                    "draft_id": "new",
                    "title": "新草稿",
                    "body": "...",
                    "generated_at": "2024-01-01T00:00:00",
                    "status": "pending",
                },
                "action_title": "新草稿标题",
                "action_data": {},
            },
        )(),
    )

    action = engine.tick()
    updated = engine.state_store.get().xhs_work_domain
    assert action is not None
    assert action.kind == "drafting"
    assert updated.state.status == XhsWorkStatus.PUBLISHING
    assert len(updated.state.pending_drafts) == 2
    assert updated.state.pending_drafts[0]["draft_id"] == "existing"
    assert updated.state.pending_drafts[1]["draft_id"] == "new"
    assert updated.state.backlog_count == 2


def test_drafting_skips_when_queue_at_capacity():
    engine = workflow_engine.XhsWorkDomainEngine(
        state_store=StateStore(),
        memory_repository=InMemoryMemoryRepository(),
    )
    domain = engine._get_or_init_domain()
    domain.state.status = XhsWorkStatus.DRAFTING
    domain.state.pending_drafts = [
        {"draft_id": f"d{i}", "title": f"草稿{i}", "body": "...", "generated_at": "2024-01-01T00:00:00", "status": "pending"}
        for i in range(workflow_engine._MAX_DRAFT_QUEUE_SIZE)
    ]
    domain.state.last_scouting_data = {
        "topics": [{"topic": "#新话题", "participation_count": "1万", "view_count": "10万"}],
        "activities": [],
    }
    engine._save(domain)

    action = engine.tick()
    updated = engine.state_store.get().xhs_work_domain
    assert action is not None
    assert action.title == "队列已满，转入发布"
    assert updated.state.status == XhsWorkStatus.PUBLISHING
    assert len(updated.state.pending_drafts) == workflow_engine._MAX_DRAFT_QUEUE_SIZE


def test_timer_fast_tracks_to_publishing_when_drafts_queued(monkeypatch):
    from datetime import datetime, timedelta, timezone

    engine = workflow_engine.XhsWorkDomainEngine(
        state_store=StateStore(),
        memory_repository=InMemoryMemoryRepository(),
    )
    domain = engine._get_or_init_domain()
    domain.state.status = XhsWorkStatus.IDLE
    domain.state.pending_drafts = [
        {"draft_id": "d1", "title": "草稿1", "body": "...", "generated_at": "2024-01-01T00:00:00", "status": "pending"}
    ]
    domain.state.last_published_at = datetime.now(timezone.utc) - timedelta(
        seconds=workflow_engine._MIN_PUBLISH_INTERVAL_SECONDS + 1
    )
    domain.state.last_scouting_at = datetime.now(timezone.utc)
    engine._save(domain)
    engine._is_first_tick = False

    monkeypatch.setattr(
        workflow_engine,
        "run_xiaohongshu_publish_pipeline",
        lambda **kwargs: type(
            "Result",
            (),
            {
                "updated_selector": None,
                "transition": type(
                    "Transition",
                    (),
                    {"kind": "publishing", "title": "已发布", "data": {}},
                )(),
            },
        )(),
    )

    action = engine.tick()
    updated = engine.state_store.get().xhs_work_domain
    assert action is not None
    assert action.kind == "publishing"
    assert updated.state.status == XhsWorkStatus.PUBLISHING


def test_timer_does_not_fast_track_if_published_too_recently():
    from datetime import datetime, timedelta, timezone

    engine = workflow_engine.XhsWorkDomainEngine(
        state_store=StateStore(),
        memory_repository=InMemoryMemoryRepository(),
    )
    domain = engine._get_or_init_domain()
    domain.state.status = XhsWorkStatus.IDLE
    domain.state.pending_drafts = [
        {"draft_id": "d1", "title": "草稿1", "body": "...", "generated_at": "2024-01-01T00:00:00", "status": "pending"}
    ]
    domain.state.last_published_at = datetime.now(timezone.utc) - timedelta(
        seconds=workflow_engine._MIN_PUBLISH_INTERVAL_SECONDS - 10
    )
    domain.state.last_scouting_at = datetime.now(timezone.utc)
    engine._save(domain)
    engine._is_first_tick = False

    action = engine.tick()
    updated = engine.state_store.get().xhs_work_domain
    assert action is None
    assert updated.state.status == XhsWorkStatus.IDLE


def test_task_chain_is_accessible():
    chain = workflow_engine.XHS_TASK_CHAIN
    assert len(chain.steps) == 6
    labels = [s.label for s in chain.steps]
    assert "侦察" in labels
    assert "发布" in labels


def test_task_chain_find_step_returns_correct_step():
    from app.domain.models import XhsTaskKind

    chain = workflow_engine.XHS_TASK_CHAIN
    step = chain.find_step(XhsTaskKind.PUBLISHING)
    assert step is not None
    assert step.label == "发布"
    assert step.can_skip is False


def test_task_chain_is_retryable():
    from app.domain.models import XhsTaskKind

    chain = workflow_engine.XHS_TASK_CHAIN

    # BLOCKED step is retryable for browser-related blockages
    assert chain.is_retryable(XhsTaskKind.BLOCKED, "浏览器器官不可用")
    assert chain.is_retryable(XhsTaskKind.BLOCKED, "页面快照失败")
    assert not chain.is_retryable(XhsTaskKind.BLOCKED, "打不开创作首页")
    assert not chain.is_retryable(XhsTaskKind.BLOCKED, "需要登录小红书账号")
    assert not chain.is_retryable(XhsTaskKind.BLOCKED, "未知错误")

    # PUBLISHING step is retryable for publish failure
    assert chain.is_retryable(XhsTaskKind.PUBLISHING, "发布失败")
    assert not chain.is_retryable(XhsTaskKind.PUBLISHING, "浏览器器官不可用")

    # Other steps are not retryable
    assert not chain.is_retryable(XhsTaskKind.SCOUTING, "页面快照失败")
    assert not chain.is_retryable(XhsTaskKind.IDLE, "任意错误")


def test_step_dispatch_via_chain():
    engine = workflow_engine.XhsWorkDomainEngine(
        state_store=StateStore(),
        memory_repository=InMemoryMemoryRepository(),
    )
    domain = engine._get_or_init_domain()

    # IDLE status → returns None (no-op step)
    domain.state.status = XhsWorkStatus.IDLE
    result = engine._step(domain)
    assert result is None
