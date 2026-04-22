from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from app.api.tool_capability_bridge import (
    BrowserCapabilityError,
    BrowserOrganUnavailable,
    call_browser_capability,
)
from app.config import get_xiaohongshu_mcp_publish_enabled, get_xiaohongshu_mcp_publish_endpoint
from app.domain.models import XhsPublishMode, XhsWorkDomainState, XhsWorkStatus
from app.external_executors.xiaohongshu_mcp_client import XiaohongshuMcpClient
from app.memory.repository import MemoryRepository
from app.runtime import StateStore
from app.usecases.xiaohongshu_browser_publish_executor import (
    execute_xiaohongshu_browser_publish,
    resolve_xiaohongshu_publish_selector,
)
from app.usecases.xiaohongshu_browser_publish_review import (
    evaluate_xiaohongshu_browser_review_preparation,
)
from app.usecases.xiaohongshu_cover_image import (
    XiaohongshuCoverImageGenerationError,
    XiaohongshuCoverImageUnavailableError,
    generate_xiaohongshu_cover_image,
)
from app.usecases.xiaohongshu_draft_generation import (
    build_xiaohongshu_opportunity_items,
    generate_xiaohongshu_draft_from_opportunity,
)
from app.usecases.xiaohongshu_publish_orchestration import (
    XiaohongshuPublishTransition,
    mark_xiaohongshu_browser_publish_success,
    mark_xiaohongshu_mcp_publish_success,
    mark_xiaohongshu_publish_blocked,
    mark_xiaohongshu_publish_review_ready,
    mark_xiaohongshu_text_image_review,
    reset_xiaohongshu_publish_to_idle,
)
from app.usecases.xiaohongshu_publish_preparation import (
    build_xiaohongshu_browser_publish_image_paths,
    find_xiaohongshu_publish_button,
    prepare_xiaohongshu_text_image_cards_for_draft,
)
from app.usecases.xiaohongshu_scouting_orchestration import (
    apply_xiaohongshu_scouting_result,
    is_xiaohongshu_creator_home_login_required,
)
from app.usecases.xiaohongshu_publish_via_mcp import publish_xiaohongshu_image_post_via_mcp
from app.usecases.xiaohongshu_text_image_autofill import autofill_xiaohongshu_text_image_cards


@dataclass
class XhsWorkDomainAction:
    kind: str  # "scouting" | "drafting" | "publishing" | "idle"
    title: str
    data: dict


_CREATOR_HOME_URL = "https://creator.xiaohongshu.com/new/home"
_PUBLISH_URL = "https://creator.xiaohongshu.com/publish/publish?from=xiao_yan&target=image"
_CREATOR_HOME_SESSION_ID = "xhs-login"


class XhsWorkDomainEngine:
    def __init__(
        self,
        state_store: StateStore,
        memory_repository: MemoryRepository,
        gateway=None,  # ChatGateway, optional for now
        mcp_client: XiaohongshuMcpClient | None = None,
    ):
        self.state_store = state_store
        self.memory_repository = memory_repository
        self.gateway = gateway
        self.mcp_client = mcp_client or XiaohongshuMcpClient(
            enabled=get_xiaohongshu_mcp_publish_enabled(),
            endpoint=get_xiaohongshu_mcp_publish_endpoint(),
        )
        # In-memory cache of last scouting result (not persisted separately)
        self._last_scouting_data: dict | None = None
        # Skip timer on first tick to avoid triggering on service startup
        self._is_first_tick = True

    def tick(self) -> XhsWorkDomainAction | None:
        """检查定时器 + 驱动状态机一步。返回当前动作或 None。"""
        domain = self._get_or_init_domain()
        # Skip timer check on very first tick to avoid triggering on service startup
        if self._is_first_tick:
            self._is_first_tick = False
        else:
            self._check_and_fire_timer(domain)
        return self._step(domain)

    def _get_or_init_domain(self) -> XhsWorkDomainState:
        state = self.state_store.get()
        if state.xhs_work_domain is None:
            state.xhs_work_domain = XhsWorkDomainState()
            self.state_store.set(state)
        return state.xhs_work_domain

    def _check_and_fire_timer(self, domain: XhsWorkDomainState) -> None:
        """检查是否该开始新一轮侦察。"""
        if domain.state.status != XhsWorkStatus.IDLE:
            return  # 已经在流程中，不重复触发
        interval_hours = domain.profile.scouting_interval_hours
        last = domain.state.last_scouting_at
        now = datetime.now(timezone.utc)
        if last is None or (now - last).total_seconds() >= interval_hours * 3600:
            domain.state.status = XhsWorkStatus.SCOUTING
            self._save(domain)

    def _step(self, domain: XhsWorkDomainState) -> XhsWorkDomainAction | None:
        status = domain.state.status
        if status == XhsWorkStatus.SCOUTING:
            return self._do_scouting(domain)
        elif status == XhsWorkStatus.DRAFTING:
            return self._do_drafting(domain)
        elif status == XhsWorkStatus.PUBLISHING:
            return self._do_publishing(domain)
        elif status == XhsWorkStatus.IDLE_REVIEWING:
            return self._do_idle_reviewing(domain)
        elif status == XhsWorkStatus.REVIEWING:
            return self._do_reviewing(domain)
        elif status == XhsWorkStatus.BLOCKED:
            return None
        return None

    def _save(self, domain: XhsWorkDomainState) -> None:
        state = self.state_store.get()
        state.xhs_work_domain = domain
        self.state_store.set(state)

    def _commit_publish_transition(
        self,
        domain: XhsWorkDomainState,
        transition: XiaohongshuPublishTransition,
    ) -> XhsWorkDomainAction:
        self._save(domain)
        return XhsWorkDomainAction(
            kind=transition.kind,
            title=transition.title,
            data=transition.data,
        )

    def _do_scouting(self, domain: XhsWorkDomainState) -> XhsWorkDomainAction:
        """browser organ 打开创作首页，提取话题和活动。"""
        try:
            open_result = call_browser_capability(
                "browser.open",
                {
                    "url": _CREATOR_HOME_URL,
                    "session_id": _CREATOR_HOME_SESSION_ID,
                    "headless": False,
                    "activate": False,
                },
                timeout_seconds=20.0,
            )
        except BrowserOrganUnavailable:
            domain.state.status = XhsWorkStatus.BLOCKED
            domain.state.current_bottleneck = "浏览器器官不可用"
            self._save(domain)
            return XhsWorkDomainAction(
                kind="scouting",
                title="侦察失败",
                data={"error": "browser organ unavailable"},
            )
        except BrowserCapabilityError:
            domain.state.status = XhsWorkStatus.BLOCKED
            domain.state.current_bottleneck = "打不开创作首页"
            self._save(domain)
            return XhsWorkDomainAction(
                kind="scouting",
                title="侦察失败",
                data={"error": "browser open failed"},
            )

        session_id = open_result.get("session_id")
        if not session_id:
            domain.state.status = XhsWorkStatus.BLOCKED
            domain.state.current_bottleneck = "打不开创作首页"
            self._save(domain)
            return XhsWorkDomainAction(
                kind="scouting",
                title="侦察失败",
                data={"error": "no session_id"},
            )

        try:
            snapshot = call_browser_capability(
                "browser.snapshot",
                {"session_id": session_id, "include_text": True},
                timeout_seconds=15.0,
            )
        except BrowserCapabilityError:
            domain.state.status = XhsWorkStatus.BLOCKED
            domain.state.current_bottleneck = "页面快照失败"
            self._save(domain)
            return XhsWorkDomainAction(
                kind="scouting",
                title="侦察失败",
                data={"error": "snapshot failed"},
            )
        finally:
            self._close_session(session_id)

        text_content = snapshot.get("text_content") or ""

        if is_xiaohongshu_creator_home_login_required(text_content):
            domain.state.status = XhsWorkStatus.BLOCKED
            domain.state.current_bottleneck = "需要登录小红书账号"
            self._save(domain)
            return XhsWorkDomainAction(
                kind="scouting",
                title="需要登录",
                data={"error": "login required"},
            )

        # Use the proper extraction function
        from app.usecases.xiaohongshu_creator_home_capture import extract_creator_home_from_raw_text
        extracted = extract_creator_home_from_raw_text(text_content)
        scouting_outcome = apply_xiaohongshu_scouting_result(
            domain,
            extracted=extracted,
            text_content=text_content,
            now=datetime.now(timezone.utc),
        )
        self._last_scouting_data = scouting_outcome.last_scouting_data
        self._save(domain)

        return XhsWorkDomainAction(
            kind="scouting",
            title=scouting_outcome.action_title,
            data=scouting_outcome.action_data,
        )

    def _do_drafting(self, domain: XhsWorkDomainState) -> XhsWorkDomainAction:
        """基于侦察结果生成草稿，放入待发布队列。"""
        if not self._last_scouting_data:
            domain.state.status = XhsWorkStatus.IDLE
            domain.state.current_focus = "无侦察数据，跳过草稿生成"
            self._save(domain)
            return XhsWorkDomainAction(kind="drafting", title="无侦察数据", data={})

        opportunity_items = build_xiaohongshu_opportunity_items(self._last_scouting_data)
        if not opportunity_items:
            domain.state.status = XhsWorkStatus.IDLE
            domain.state.current_focus = "未发现话题或活动"
            self._save(domain)
            return XhsWorkDomainAction(kind="drafting", title="无机会内容", data={})

        opportunity = opportunity_items[0]
        draft_outcome = generate_xiaohongshu_draft_from_opportunity(
            opportunity,
            gateway=self.gateway,
            build_prompt=self._build_draft_prompt,
        )
        domain.state.pending_drafts = [draft_outcome.draft]
        domain.state.status = XhsWorkStatus.PUBLISHING
        domain.state.backlog_count = 1
        self._save(domain)

        return XhsWorkDomainAction(
            kind="drafting",
            title=draft_outcome.action_title,
            data=draft_outcome.action_data,
        )

    def _do_publishing(self, domain: XhsWorkDomainState) -> XhsWorkDomainAction:
        """从队列取草稿，通过 browser.publish 发布。"""
        drafts = domain.state.pending_drafts
        if not drafts:
            self._clear_review_session(domain)
            return self._commit_publish_transition(domain, reset_xiaohongshu_publish_to_idle(domain))

        self._clear_review_session(domain)
        draft = drafts[0]
        browser_image_paths: list[str] = []
        requires_manual_review = self._requires_manual_publish_review(domain)

        mcp_result = None if requires_manual_review else self._publish_draft_via_mcp(draft)
        if mcp_result is not None:
            browser_image_paths = [str(item).strip() for item in mcp_result.image_paths if str(item).strip()]
            status = mcp_result.status
            if status not in {
                "publisher_disabled",
                "service_unreachable",
                "publish_failed",
                "cover_generation_failed",
                "cover_generation_unavailable",
            }:
                return self._commit_publish_transition(
                    domain,
                    mark_xiaohongshu_mcp_publish_success(
                        domain,
                        drafts=drafts,
                        draft=draft,
                        post_url=mcp_result.post_url or _PUBLISH_URL,
                        message=mcp_result.message,
                        image_paths=mcp_result.image_paths,
                    ),
                )
        if not browser_image_paths:
            browser_image_paths = build_xiaohongshu_browser_publish_image_paths(
                draft,
                generate_cover_image=generate_xiaohongshu_cover_image,
            )

        selector_resolution = resolve_xiaohongshu_publish_selector(
            requires_manual_review=requires_manual_review,
            auto_publish_selector=domain.profile.auto_publish_selector,
            find_publish_button=lambda: find_xiaohongshu_publish_button(
                publish_url=_PUBLISH_URL,
                call_browser_capability=call_browser_capability,
                close_session=self._close_session,
            ),
            prepare_text_image_cards=lambda: prepare_xiaohongshu_text_image_cards_for_draft(
                draft,
                autofill_cards=autofill_xiaohongshu_text_image_cards,
            ),
        )
        if selector_resolution.text_image_result is not None:
            status = selector_resolution.text_image_result.get("status", "missing_editor")
            if status == "browser_unavailable":
                return self._commit_publish_transition(
                    domain,
                    mark_xiaohongshu_publish_blocked(
                        domain,
                        bottleneck="浏览器器官不可用",
                        title="发布失败",
                        data={"error": "browser organ unavailable"},
                    ),
                )
            return self._commit_publish_transition(
                domain,
                mark_xiaohongshu_text_image_review(
                    domain,
                    focus=str(
                        selector_resolution.text_image_result.get("focus")
                        or "已进入补图阶段，等待图片生成后再继续发布"
                    ),
                    status=status,
                    message=selector_resolution.text_image_result.get("message", ""),
                ),
            )
        if selector_resolution.blocked_reason:
            return self._commit_publish_transition(
                domain,
                mark_xiaohongshu_publish_blocked(
                    domain,
                    bottleneck=selector_resolution.blocked_reason,
                    title="发布失败",
                    data={"error": "publish button not found"},
                ),
            )
        selector = selector_resolution.selector
        if selector and selector != domain.profile.auto_publish_selector and not requires_manual_review:
            domain.profile.auto_publish_selector = selector
            self._save(domain)

        execution = execute_xiaohongshu_browser_publish(
            title=str(draft.get("title", "")),
            body=str(draft.get("body", "")),
            selector=selector,
            image_paths=browser_image_paths,
            open_publish_page=lambda: call_browser_capability(
                "browser.open",
                {"url": _PUBLISH_URL, "headless": False},
                timeout_seconds=20.0,
            ),
            publish_to_page=lambda session_id, title, body, publish_selector, image_paths: call_browser_capability(
                "browser.publish",
                {
                    "session_id": session_id,
                    "title": title,
                    "body": body,
                    "publish_selector": publish_selector,
                    "image_paths": image_paths,
                },
                timeout_seconds=20.0,
            ),
        )
        session_id = execution.session_id
        if execution.error:
            if session_id:
                self._close_session(session_id)
            return self._commit_publish_transition(
                domain,
                mark_xiaohongshu_publish_blocked(
                    domain,
                    bottleneck=execution.blocked_reason or "发布失败",
                    title="发布失败",
                    data={"error": execution.error},
                ),
            )
        if not session_id:
            return self._commit_publish_transition(
                domain,
                mark_xiaohongshu_publish_blocked(
                    domain,
                    bottleneck=execution.blocked_reason or "无法打开发布页",
                    title="打开发布页失败",
                    data={},
                ),
            )

        publish_result = execution.publish_result or {}
        publish_clicked = publish_result.get("publish_clicked", False)
        status = publish_result.get("status", "unknown")

        if requires_manual_review:
            if status == "awaiting_image_upload" and not browser_image_paths:
                text_image_result = prepare_xiaohongshu_text_image_cards_for_draft(
                    draft,
                    autofill_cards=autofill_xiaohongshu_text_image_cards,
                )
                if text_image_result is not None:
                    review_status = text_image_result.get("status", "missing_editor")
                    if review_status == "browser_unavailable":
                        self._close_session(session_id)
                        return self._commit_publish_transition(
                            domain,
                            mark_xiaohongshu_publish_blocked(
                                domain,
                                bottleneck="浏览器器官不可用",
                                title="发布失败",
                                data={"error": "browser organ unavailable"},
                            ),
                        )
                    self._close_session(session_id)
                    return self._commit_publish_transition(
                        domain,
                        mark_xiaohongshu_text_image_review(
                            domain,
                            focus=str(
                                text_image_result.get("focus")
                                or "已进入补图阶段，等待图片生成后再继续发布"
                            ),
                            status=review_status,
                            message=text_image_result.get("message", ""),
                        ),
                    )
            review_preparation = evaluate_xiaohongshu_browser_review_preparation(
                publish_result=publish_result,
                requested_image_paths=browser_image_paths,
            )
            if review_preparation.ready:
                return self._commit_publish_transition(
                    domain,
                    mark_xiaohongshu_publish_review_ready(
                        domain,
                        draft=draft,
                        session_id=session_id,
                        focus=review_preparation.focus,
                        next_action=review_preparation.next_action,
                        status=status,
                        uploaded_image_count=int(publish_result.get("uploaded_image_count", 0) or 0),
                    ),
                )
            self._close_session(session_id)
            return self._commit_publish_transition(
                domain,
                mark_xiaohongshu_publish_blocked(
                    domain,
                    bottleneck=review_preparation.blocking_reason or "还没准备到可发布状态",
                    title="发布前准备失败",
                    data={"status": status},
                ),
            )
        if publish_clicked:
            self._close_session(session_id)
            return self._commit_publish_transition(
                domain,
                mark_xiaohongshu_browser_publish_success(
                    domain,
                    drafts=drafts,
                    draft=draft,
                    post_url=_PUBLISH_URL,
                    current_focus="已自动补封面并发布成功" if browser_image_paths else "已完成补图并发布成功",
                ),
            )
        self._close_session(session_id)
        return self._commit_publish_transition(
            domain,
            mark_xiaohongshu_publish_blocked(
                domain,
                bottleneck=f"无法点击发布按钮（status={status}）",
                title="发布未完成",
                data={"status": status},
            ),
        )

    def _do_idle_reviewing(self, domain: XhsWorkDomainState) -> XhsWorkDomainAction | None:
        drafts = domain.state.pending_drafts
        if not drafts:
            domain.state.status = XhsWorkStatus.IDLE
            domain.state.current_focus = "补图阶段已结束"
            domain.state.current_bottleneck = ""
            domain.state.next_recommended_action = ""
            self._save(domain)
            return XhsWorkDomainAction(kind="idle", title="补图完成", data={})

        domain.state.status = XhsWorkStatus.PUBLISHING
        domain.state.current_focus = "检测到仍有待发草稿，继续完成发布"
        domain.state.current_bottleneck = ""
        domain.state.next_recommended_action = ""
        self._save(domain)
        return self._do_publishing(domain)

    def _do_reviewing(self, _domain: XhsWorkDomainState) -> XhsWorkDomainAction | None:
        return None

    def _publish_draft_via_mcp(self, draft: dict):
        title = str(draft.get("title", "")).strip()
        body = str(draft.get("body", "")).strip()
        if not title or not body:
            return None
        raw_image_paths = draft.get("image_paths")
        image_paths = raw_image_paths if isinstance(raw_image_paths, list) else []
        return publish_xiaohongshu_image_post_via_mcp(
            title=title,
            body=body,
            image_paths=image_paths,
            client=self.mcp_client,
        )

    def _close_session(self, session_id: str) -> None:
        if session_id == _CREATOR_HOME_SESSION_ID:
            return
        try:
            call_browser_capability(
                "browser.close",
                {"session_id": session_id},
                timeout_seconds=5.0,
            )
        except Exception:
            pass

    def _clear_review_session(self, domain: XhsWorkDomainState) -> None:
        session_id = domain.state.review_session_id.strip()
        if not session_id:
            return
        domain.state.review_session_id = ""
        self._close_session(session_id)

    def _requires_manual_publish_review(self, domain: XhsWorkDomainState) -> bool:
        return domain.profile.publish_mode == XhsPublishMode.REVIEW_BEFORE_PUBLISH

    def _build_draft_prompt(self, opportunity: dict) -> str:
        title = opportunity.get("title", "")
        summary = opportunity.get("summary", "")
        source_kind = opportunity.get("source_kind", "topic")
        return (
            "你现在不是在写运营建议，也不是在写方法论说明，而是在直接写一篇可以人工确认后发布的小红书图文稿。\n"
            "要求：\n"
            "1. 语言像真人发笔记，少抽象词，少空话。\n"
            "2. 必须写出一个明确场景、一个明确问题、一个明确动作。\n"
            '3. 禁止出现"最小闭环""验证反馈""轻量转化""先跑通"这类产品黑话。\n'
            "4. 不要写成课程大纲，不要写成写作指导。\n"
            "5. 输出必须严格使用下面格式。\n\n"
            f"机会来源：{source_kind}\n"
            f"机会标题：{title}\n"
            f"补充信息：{summary}\n\n"
            "请严格输出：\n"
            "标题：...\n\n正文：...\n"
        )

    def _extract_topics_and_activities(self, text: str) -> tuple[list[str], list[str]]:
        """从页面文本中提取话题和活动。简单实现。"""
        lines = text.split("\n")
        topics, activities = [], []
        current_section = None
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            lower = stripped.lower()
            if "话题" in lower or "topic" in lower:
                current_section = "topics"
                continue
            if "活动" in lower or "campaign" in lower:
                current_section = "activities"
                continue
            if current_section == "topics" and len(stripped) < 100:
                topics.append(stripped)
            elif current_section == "activities" and len(stripped) < 200:
                activities.append(stripped)
        return topics[:10], activities[:5]
