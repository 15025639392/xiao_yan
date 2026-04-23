from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from app.api.tool_capability_bridge import (
    BrowserCapabilityError,
    BrowserOrganUnavailable,
    call_browser_capability,
)
from app.domain.models import (
    XhsPublishMode,
    XhsTaskChain,
    XhsTaskKind,
    XhsTaskStep,
    XhsWorkDomainState,
    XhsWorkStatus,
)
from app.memory.repository import MemoryRepository
from app.runtime import StateStore
from app.usecases.xiaohongshu_draft_generation import (
    build_xiaohongshu_opportunity_items,
    generate_xiaohongshu_draft_from_opportunity,
)
from app.usecases.xiaohongshu_content_strategy import (
    build_xiaohongshu_creator_home_prompt as build_creator_home_content_prompt,
)
from app.usecases.xiaohongshu_publish_orchestration import (
    XiaohongshuPublishTransition,
    reset_xiaohongshu_publish_to_idle,
)
from app.usecases.xiaohongshu_publish_pipeline import (
    run_xiaohongshu_publish_pipeline,
)
from app.usecases.xiaohongshu_scouting_orchestration import (
    apply_xiaohongshu_scouting_result,
    is_xiaohongshu_creator_home_login_required,
)
from app.usecases.xiaohongshu_policy import can_post_today, check_draft_against_policy


@dataclass
class XhsWorkDomainAction:
    kind: str  # "scouting" | "drafting" | "publishing" | "idle"
    title: str
    data: dict


_CREATOR_HOME_URL = "https://creator.xiaohongshu.com/new/home"
_PUBLISH_URL = "https://creator.xiaohongshu.com/publish/publish?from=xiao_yan&target=image"
_CREATOR_HOME_SESSION_ID = "xhs-login"

_BLOCKED_RETRY_SECONDS = 300
_MIN_PUBLISH_INTERVAL_SECONDS = 300
_MAX_DRAFTS_PER_SCOUTING = 2
_MAX_DRAFT_QUEUE_SIZE = 3

# Canonical task chain — drives step dispatch and retryable-blockage lookups.
XHS_TASK_CHAIN = XhsTaskChain()


class XhsWorkDomainEngine:
    def __init__(
        self,
        state_store: StateStore,
        memory_repository: MemoryRepository,
        gateway=None,  # ChatGateway, optional for now
    ):
        self.state_store = state_store
        self.memory_repository = memory_repository
        self.gateway = gateway
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
        """检查是否该开始新一轮侦察，或对可恢复的 BLOCKED 自动重试。"""
        now = datetime.now(timezone.utc)
        if domain.state.status == XhsWorkStatus.BLOCKED:
            if (
                XHS_TASK_CHAIN.is_retryable(XhsTaskKind.BLOCKED, domain.state.blocked_reason)
                and domain.state.blocked_at is not None
                and (now - domain.state.blocked_at).total_seconds() >= _BLOCKED_RETRY_SECONDS
            ):
                domain.state.status = XhsWorkStatus.IDLE
                domain.state.current_bottleneck = ""
                domain.state.blocked_reason = ""
                domain.state.next_recommended_action = ""
                self._save(domain)
            return
        if domain.state.status != XhsWorkStatus.IDLE:
            return  # 已经在流程中，不重复触发
        # Fast-track to publishing if there are queued drafts and enough time has passed
        if domain.profile.publish_mode == XhsPublishMode.AUTO and domain.state.pending_drafts:
            last_published = domain.state.last_published_at
            if last_published is None or (now - last_published).total_seconds() >= _MIN_PUBLISH_INTERVAL_SECONDS:
                domain.state.status = XhsWorkStatus.PUBLISHING
                domain.state.current_focus = "队列中有待发草稿，继续发布"
                self._save(domain)
                return
        interval_hours = domain.profile.scouting_interval_hours
        last = domain.state.last_scouting_at
        if last is None or (now - last).total_seconds() >= interval_hours * 3600:
            domain.state.status = XhsWorkStatus.SCOUTING
            self._save(domain)

    def _step(self, domain: XhsWorkDomainState) -> XhsWorkDomainAction | None:
        """Dispatch to the handler for the current status, as defined by XHS_TASK_CHAIN."""
        status = domain.state.status
        step = XHS_TASK_CHAIN.find_step(XhsTaskKind(status.value))
        if step is None:
            return None
        return self._dispatch_step(step, domain)

    def _dispatch_step(
        self,
        step: XhsTaskStep,
        domain: XhsWorkDomainState,
    ) -> XhsWorkDomainAction | None:
        """Execute the handler for the given task step."""
        dispatch = {
            XhsTaskKind.SCOUTING: self._do_scouting,
            XhsTaskKind.DRAFTING: self._do_drafting,
            XhsTaskKind.PUBLISHING: self._do_publishing,
            XhsTaskKind.REVIEWING: self._do_reviewing,
            XhsTaskKind.BLOCKED: lambda _: None,
            XhsTaskKind.IDLE: lambda _: None,
        }
        handler = dispatch.get(step.kind)
        if handler is None:
            return None
        return handler(domain)

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
            now = datetime.now(timezone.utc)
            domain.state.status = XhsWorkStatus.BLOCKED
            domain.state.current_bottleneck = "浏览器器官不可用"
            domain.state.blocked_at = now
            domain.state.blocked_reason = "浏览器器官不可用"
            self._save(domain)
            return XhsWorkDomainAction(
                kind="scouting",
                title="侦察失败",
                data={"error": "browser organ unavailable"},
            )
        except BrowserCapabilityError:
            now = datetime.now(timezone.utc)
            domain.state.status = XhsWorkStatus.BLOCKED
            domain.state.current_bottleneck = "打不开创作首页"
            domain.state.blocked_at = now
            domain.state.blocked_reason = "打不开创作首页"
            self._save(domain)
            return XhsWorkDomainAction(
                kind="scouting",
                title="侦察失败",
                data={"error": "browser open failed"},
            )

        session_id = open_result.get("session_id")
        if not session_id:
            now = datetime.now(timezone.utc)
            domain.state.status = XhsWorkStatus.BLOCKED
            domain.state.current_bottleneck = "打不开创作首页"
            domain.state.blocked_at = now
            domain.state.blocked_reason = "打不开创作首页"
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
            now = datetime.now(timezone.utc)
            domain.state.status = XhsWorkStatus.BLOCKED
            domain.state.current_bottleneck = "页面快照失败"
            domain.state.blocked_at = now
            domain.state.blocked_reason = "页面快照失败"
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
            now = datetime.now(timezone.utc)
            domain.state.status = XhsWorkStatus.BLOCKED
            domain.state.current_bottleneck = "需要登录小红书账号"
            domain.state.blocked_at = now
            domain.state.blocked_reason = "需要登录小红书账号"
            self._save(domain)
            return XhsWorkDomainAction(
                kind="scouting",
                title="需要登录",
                data={"error": "login required"},
            )

        # Use the proper extraction function
        from app.usecases.xiaohongshu_creator_home_capture import extract_creator_home_from_raw_text
        extracted = extract_creator_home_from_raw_text(text_content)

        # Try to fetch engagement metrics for the most recent published post
        history = domain.state.published_history
        if history:
            last_entry = history[-1]
            post_url = last_entry.get("post_url", "")
            if post_url:
                metrics_updated = _try_fetch_metrics(session_id, post_url, history)
                if metrics_updated is not None:
                    domain.state.published_history = metrics_updated

        scouting_outcome = apply_xiaohongshu_scouting_result(
            domain,
            extracted=extracted,
            text_content=text_content,
            now=datetime.now(timezone.utc),
        )
        self._save(domain)

        return XhsWorkDomainAction(
            kind="scouting",
            title=scouting_outcome.action_title,
            data=scouting_outcome.action_data,
        )

    def _do_drafting(self, domain: XhsWorkDomainState) -> XhsWorkDomainAction:
        """基于侦察结果生成草稿，放入待发布队列。"""
        if not domain.state.last_scouting_data:
            domain.state.status = XhsWorkStatus.IDLE
            domain.state.current_focus = "无侦察数据，跳过草稿生成"
            self._save(domain)
            return XhsWorkDomainAction(kind="drafting", title="无侦察数据", data={})

        opportunity_items = build_xiaohongshu_opportunity_items(
            domain.state.last_scouting_data,
            domain.state.published_history,
            recent_topics=domain.memory.successful_topic_titles,
        )
        if not opportunity_items:
            domain.state.status = XhsWorkStatus.IDLE
            domain.state.current_focus = "未发现话题或活动"
            self._save(domain)
            return XhsWorkDomainAction(kind="drafting", title="无机会内容", data={})

        current_drafts = domain.state.pending_drafts
        if len(current_drafts) >= _MAX_DRAFT_QUEUE_SIZE:
            domain.state.status = XhsWorkStatus.PUBLISHING
            domain.state.current_focus = f"草稿队列已满 ({_MAX_DRAFT_QUEUE_SIZE})，优先发布"
            self._save(domain)
            return XhsWorkDomainAction(kind="drafting", title="队列已满，转入发布", data={})

        new_drafts = []
        titles = []
        error_count = 0
        warning_count = 0
        for opportunity in opportunity_items[:_MAX_DRAFTS_PER_SCOUTING]:
            draft_outcome = generate_xiaohongshu_draft_from_opportunity(
                opportunity,
                gateway=self.gateway,
                build_prompt=self._build_draft_prompt,
            )
            draft = draft_outcome.draft
            # Validate against work policy
            check = check_draft_against_policy(draft, domain.policy)
            if not check.ok:
                # Mark draft as policy-rejected; still queue it but flag the violations
                draft["policy_rejected"] = True
                draft["policy_violations"] = [v.message for v in check.errors]
                error_count += 1
            for w in check.warnings:
                draft.setdefault("policy_warnings", []).append(w.message)
                warning_count += 1
            new_drafts.append(draft)
            titles.append(draft_outcome.action_title)

        domain.state.pending_drafts = current_drafts + new_drafts
        domain.state.backlog_count = len(domain.state.pending_drafts)
        if domain.profile.publish_mode == XhsPublishMode.AUTO:
            domain.state.status = XhsWorkStatus.PUBLISHING
            domain.state.current_focus = "草稿已生成，开始自动发布"
            domain.state.next_recommended_action = ""
        else:
            domain.state.status = XhsWorkStatus.IDLE
            domain.state.current_focus = f"已生成 {len(new_drafts)} 条草稿，等待手动发布"
            domain.state.next_recommended_action = "请在待发草稿列表中选择一条并点击发布。"
        self._save(domain)

        return XhsWorkDomainAction(
            kind="drafting",
            title=f"生成 {len(new_drafts)} 条草稿",
            data={
                "drafts": [{"title": t} for t in titles],
                "policy_errors": error_count,
                "policy_warnings": warning_count,
            },
        )

    def _do_publishing(self, domain: XhsWorkDomainState) -> XhsWorkDomainAction:
        """从队列取草稿，通过标准人工确认发布链完成发布前准备。"""
        drafts = domain.state.pending_drafts
        if not drafts:
            self._clear_review_session(domain)
            return self._commit_publish_transition(domain, reset_xiaohongshu_publish_to_idle(domain))

        # Policy check: daily post limit
        today_count = self._count_posts_today(domain)
        if not can_post_today(today_count, domain.policy):
            # Consume this draft so the queue advances (don't re-enter on next tick)
            skipped_draft = drafts[0]
            domain.state.pending_drafts = drafts[1:]
            domain.state.backlog_count = len(domain.state.pending_drafts)
            skipped_draft["status"] = "skipped_policy"
            skipped_draft["skip_reason"] = "daily_limit"
            domain.state.status = XhsWorkStatus.IDLE
            domain.state.current_focus = (
                f"今日发布次数已达上限（{domain.policy.max_posts_per_day}），"
                f"跳过草稿「{skipped_draft.get('title', '(无标题)')}」"
            )
            domain.state.current_bottleneck = ""
            self._save(domain)
            return XhsWorkDomainAction(
                kind="publishing",
                title="发布频率超限，已跳过草稿",
                data={"skipped_draft": skipped_draft.get("draft_id"), "limit": domain.policy.max_posts_per_day},
            )

        self._clear_review_session(domain)
        draft = drafts[0]

        try:
            result = run_xiaohongshu_publish_pipeline(
                domain=domain,
                drafts=drafts,
                draft=draft,
                publish_mode=domain.profile.publish_mode,
                publish_url=_PUBLISH_URL,
                call_browser_capability=call_browser_capability,
                close_session=self._close_session,
            )
        except Exception as exc:  # noqa: BLE001
            # Unexpected exception in the publish pipeline — treat as a recoverable BLOCKED
            domain.state.status = XhsWorkStatus.BLOCKED
            domain.state.current_bottleneck = f"发布管道异常：{exc}"
            domain.state.blocked_reason = "发布失败"
            domain.state.blocked_at = datetime.now(timezone.utc)
            self._save(domain)
            return XhsWorkDomainAction(
                kind="publishing",
                title="发布管道异常",
                data={"error": str(exc)},
            )

        return self._commit_publish_transition(domain, result.transition)

    def _do_reviewing(self, domain: XhsWorkDomainState) -> XhsWorkDomainAction | None:
        """Handle REVIEWING: check for review timeout and auto-continue."""
        if not domain.state.review_session_id:
            # No active review session — just return to idle
            domain.state.status = XhsWorkStatus.IDLE
            domain.state.current_focus = "无待审核会话"
            domain.state.review_started_at = None
            self._save(domain)
            return XhsWorkDomainAction(kind="idle", title="审核会话已结束", data={})

        timeout_minutes = domain.policy.review_timeout_minutes
        if timeout_minutes <= 0:
            return None  # timeout disabled

        # Check if review session has timed out
        # We track when the review started implicitly via review_session_id presence
        # For a proper timeout, we'd need review_started_at — check if it exists
        review_started_at = getattr(domain.state, "review_started_at", None)
        if review_started_at:
            from datetime import timedelta

            elapsed = datetime.now(timezone.utc) - review_started_at
            if elapsed.total_seconds() >= timeout_minutes * 60:
                # Timeout: consume the draft (user didn't confirm) and return to idle
                drafts = domain.state.pending_drafts
                if drafts:
                    timed_out_draft = drafts[0]
                    timed_out_draft["status"] = "review_timeout"
                    domain.state.pending_drafts = drafts[1:]
                    domain.state.backlog_count = len(domain.state.pending_drafts)
                domain.state.status = XhsWorkStatus.IDLE
                domain.state.current_focus = f"审核超时（>{timeout_minutes}分钟），已跳过草稿"
                domain.state.review_session_id = ""
                domain.state.review_started_at = None
                self._save(domain)
                return XhsWorkDomainAction(
                    kind="reviewing",
                    title="审核超时跳过",
                    data={"draft_id": timed_out_draft.get("draft_id") if drafts else None},
                )
        return None

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

    def _count_posts_today(self, domain: XhsWorkDomainState) -> int:
        """Count how many posts were published today (UTC)."""
        today = datetime.now(timezone.utc).date()
        return sum(
            1 for entry in domain.state.published_history
            if entry.get("published_at")
            and datetime.fromisoformat(entry["published_at"]).date() == today
        )

    def _try_fetch_metrics(
        self,
        scout_session_id: str,
        post_url: str,
        history: list[dict],
    ) -> list[dict] | None:
        """Attempt to fetch engagement metrics for the most recent published post.

        Opens the post URL in the scouting session, captures metrics from the
        rendered page, then navigates back to the creator home. Silently returns
        None on any error so scouting is never blocked by metrics failures.
        """
        try:
            from app.usecases.xiaohongshu_metrics_capture import fetch_metrics_for_history

            return fetch_metrics_for_history(history, session_id=scout_session_id, post_url=post_url)
        except Exception:
            return None

    def _clear_review_session(self, domain: XhsWorkDomainState) -> None:
        session_id = domain.state.review_session_id.strip()
        if not session_id:
            return
        domain.state.review_session_id = ""
        domain.state.review_started_at = None
        self._close_session(session_id)

    def _build_draft_prompt(self, opportunity: dict) -> str:
        title = opportunity.get("title", "")
        summary = opportunity.get("summary", "")
        source_kind = opportunity.get("source_kind", "topic")
        domain = self._get_or_init_domain()
        persona_lines = []
        if domain.profile.account_positioning:
            persona_lines.append(f"账号定位：{domain.profile.account_positioning}")
        if domain.profile.target_audience:
            persona_lines.append(f"目标受众：{domain.profile.target_audience}")
        if domain.profile.expression_style:
            persona_lines.append(f"表达风格：{domain.profile.expression_style}")
        persona_section = "\n".join(persona_lines)
        if persona_section:
            persona_section = "\n" + persona_section + "\n"
        memory_lines = []
        if domain.memory.recent_draft_titles:
            memory_lines.append(
                "近期已发布标题（请避免重复类似主题）："
                + "、".join(domain.memory.recent_draft_titles)
            )
        if domain.memory.successful_topic_titles:
            memory_lines.append(
                "近期成功话题：" + "、".join(domain.memory.successful_topic_titles)
            )
        memory_section = "\n".join(memory_lines)
        if memory_section:
            memory_section = memory_section + "\n"
        return build_creator_home_content_prompt(
            source_kind=source_kind,
            source_title=title,
            source_summary=summary,
            persona_section=persona_section,
            memory_section=memory_section,
            structured_output=False,
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
